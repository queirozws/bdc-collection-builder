#
# This file is part of Brazil Data Cube Collection Builder.
# Copyright (C) 2019-2020 INPE.
#
# Brazil Data Cube Collection Builder is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
#

"""Define base interface for Celery Tasks."""


# Python Native
from datetime import datetime
# 3rdparty
from bdc_catalog.models import Collection, Provider
from bdc_collectors.ext import CollectorExtension, BaseProvider
from flask import current_app
from celery import chain, group
from celery.backends.database import Task
from sqlalchemy import func, Date
from werkzeug.exceptions import BadRequest
# Builder
from ..config import Config
from ..celery.tasks import download, correction, publish, post
from .forms import RadcorActivityForm, SimpleActivityForm
from .models import RadcorActivity, RadcorActivityHistory, db
from .utils import get_or_create_model

from .models import ActivitySRC

# Consts
CLOUD_DEFAULT = 100
DESTINATION_DIR = Config.DATA_DIR


class RadcorBusiness:
    """Define an interface for handling entire module business."""

    @classmethod
    def start(cls, activity, skip_l1=None, **kwargs):
        """Dispatch the celery tasks."""
        activity['args'].update(kwargs)
        return dispatch(activity, skip_l1, **kwargs)

    @classmethod
    def restart(cls, ids=None, status=None, activity_type=None, sceneid=None, collection_id=None, action=None, **kwargs):
        """Restart celery task execution.

        Args:
            ids - List of Activity ID
            status - Filter by task status
            activity_type - Filter by activity type

        Returns:
            Affected activities
        """
        restrictions = []

        if ids:
            restrictions.append(RadcorActivity.id.in_(ids))

        if status:
            restrictions.append(RadcorActivityHistory.task.has(status=status))

        if activity_type:
            restrictions.append(RadcorActivity.activity_type == activity_type)

        if collection_id:
            restrictions.append(RadcorActivity.collection_id == collection_id)

        if sceneid:
            if collection_id is None or activity_type is None:
                raise BadRequest('The parameters "collection_id" and "activity_type" are required to search by sceneid.')

            scenes = sceneid.split(',') if isinstance(sceneid, str) else sceneid
            restrictions.append(RadcorActivity.sceneid.in_(scenes))

        if len(restrictions) == 0:
            raise BadRequest('Invalid restart. You must provide query restriction such "ids", "activity_type" or "status"')

        activities = db.session.query(RadcorActivity).filter(*restrictions).all()

        # Define a start wrapper in order to preview or start activity
        start_activity = cls.dispatch if str(action).lower() == 'start' else lambda _: _

        serialized_activities = SimpleActivityForm().dump(activities, many=True)

        for activity in serialized_activities:
            start_activity(activity['id'])

        # for activity in serialized_activities:
        #     activity['args'].update(kwargs)
        #     start_activity(activity)

        return serialized_activities

    @classmethod
    def create_activity(cls, activity, parent=None):
        """Persist an activity on database."""
        where = dict(
            sceneid=activity['sceneid'],
            activity_type=activity['activity_type'],
            collection_id=activity['collection_id']
        )

        model, created = get_or_create_model(RadcorActivity, defaults=activity, **where)

        if created:
            db.session.add(model)

        if parent:
            relation_defaults = dict(
                activity=model,
                parent=parent
            )

            _relation, _created = get_or_create_model(
                ActivitySRC,
                defaults=relation_defaults,
                **relation_defaults
            )

        return model, created

    @classmethod
    def dispatch(cls, activity_id, skip_collection_id=None):
        """Search by activity and dispatch the respective task.

        TODO: Support object to skip tasks using others values.

        Args:
            activity_id - Activity Identifier
            skip_collection_id - Skip the tasks with has the given collection id.
        """
        act = RadcorActivity.query().filter(RadcorActivity.id == activity_id).first()

        if act is None:
            raise RuntimeError(f'Not found activity {activity_id}')

        def _dispatch_task(activity):
            dump = RadcorActivityForm().dump(activity)

            task = cls._task_definition(activity.activity_type).si(dump)

            if not activity.children:
                return task

            tasks = []

            for child in activity.children:
                if skip_collection_id == child.activity.collection_id:
                    continue

                tasks.append(_dispatch_task(child.activity))

            return task | chain(*tasks)

        task = _dispatch_task(act)
        task.apply_async()

    @classmethod
    def _task_definition(cls, task_type):
        """Get a task by string.

        TODO: We should consider to import dynamically using importlib or factory method.
        """
        if task_type == 'download':
            _task = download
        elif task_type == 'correction':
            _task = correction
        elif task_type == 'publish':
            _task = publish
        elif task_type == 'post':
            _task = post
        else:
            raise RuntimeError(f'Task {task_type} not supported.')

        return _task

    @classmethod
    def _activity_definition(cls, collection_id, activity_type, scene, **kwargs):
        return dict(
            collection_id=collection_id,
            activity_type=activity_type,
            tags=kwargs.get('tags', []),
            sceneid=scene.scene_id,
            scene_type='SCENE',
            args=dict(
                cloud=scene.cloud_cover,
                **kwargs
            )
        )

    @classmethod
    def radcor(cls, args: dict):
        """Search for Landsat/Sentinel Images and dispatch download task."""
        args.setdefault('limit', 299)
        args.setdefault('cloud', CLOUD_DEFAULT)

        # Get bbox
        w = float(args['w'])
        e = float(args['e'])
        s = float(args['s'])
        n = float(args['n'])
        bbox = [w, s, e, n]

        cloud = float(args['cloud'])
        action = args.get('action', 'preview')

        collections = Collection.query().filter(Collection.collection_type == 'collection').all()

        # TODO: Review this code. The collection name is not unique anymore.
        collections_map = {c.name: c.id for c in collections}

        tasks = args.get('tasks', [])

        try:
            collector_extension: CollectorExtension = current_app.extensions['bdc:collector']

            catalog_provider: Provider = Provider.query().filter(Provider.name == args['catalog']).first_or_404()

            provider_class = collector_extension.get_provider(catalog_provider.name)

            provider: BaseProvider = provider_class(**catalog_provider.credentials)

            result = provider.search(
                query=args['dataset'],
                bbox=bbox,
                start_date=args['start'],
                end_date=args['end'],
                cloud_cover=cloud
            )

            def _recursive(scene, task, parent=None, parallel=True, pass_args=True):
                collection_id = collections_map[task['collection']]

                activity = cls._activity_definition(collection_id, task['type'], scene, **task['args'])
                activity['args'].update(dict(catalog=args['catalog'], dataset=args['dataset']))

                _task = cls._task_definition(task['type'])

                instance, created = cls.create_activity(activity, parent)
                dump = RadcorActivityForm().dump(instance)
                dump['args'].update(activity['args'])

                keywords = dict(collection_id=collection_id, activity_type=task['type'])

                if not task.get('tasks'):
                    return _task.s(**keywords)

                res = []

                for child in task['tasks']:
                    # When triggering children, use parallel=False to use chain workflow
                    res.append(_recursive(scene, child, parent=instance, parallel=False, pass_args=False))

                handler = group(*res) if parallel else chain(*res)

                arguments = []

                if pass_args:
                    arguments.append(dump)

                return _task.s(*arguments, **keywords) | handler

            if action == 'start':
                to_dispatch = []

                with db.session.begin_nested():
                    for scene_result in result:
                        for task in tasks:
                            if task['type'] == 'download':
                                cls.validate_provider(collections_map[task['collection']])

                            children_task = _recursive(scene_result, task, parent=None)

                            to_dispatch.append(children_task)

                db.session.commit()

                group(to_dispatch).apply_async()
        except BaseException:
            db.session.rollback()
            raise

        return result

    @classmethod
    def validate_provider(cls, collection_id):
        collection = Collection.query().filter(Collection.id == collection_id).first_or_404()

        collector_extension: CollectorExtension = current_app.extensions['bdc:collector']

        download_order = collector_extension.get_provider_order(collection)

        if len(download_order) == 0:
            raise RuntimeError(f'Collection {collection.name} does not have any data provider set.')

    @classmethod
    def list_activities(cls, args: dict):
        """List task activities from database."""
        filters = []
        if args.get('scene_id'):
            filters.append(RadcorActivity.sceneid == args['scene_id'])
        if args.get('collection'):
            filters.append(RadcorActivity.collection_id == args['collection'])
        if args.get('type'):
            filters.append(RadcorActivity.activity_type.contains(args['type']))
        if args.get('period'):
            dates = args['period'].split('/')
            if len(dates) != 2:
                raise BadRequest('Incorrect dates! Format: YYYY-mm-dd/YYYY-mm-dd')
            filters.append(RadcorActivity.history.any(
                    RadcorActivityHistory.start >= datetime.strptime(dates[0], '%Y-%m-%d')))
            filters.append(RadcorActivity.history.any(
                    RadcorActivityHistory.start <= datetime.strptime(dates[1]+' 23:59', '%Y-%m-%d %H:%M')))

        activities = RadcorActivity.query().filter(*filters)
        return activities

    @classmethod
    def count_activities(cls, args: dict):
        """Count grouped by status on database."""
        filters = []
        if args.get('start_date'): filters.append(RadcorActivityHistory.start >= '{}T00:00'.format(args['start_date']))
        if args.get('last_date'): filters.append(RadcorActivityHistory.start <= '{}T23:59'.format(args['last_date']))
        if args.get('collection'): filters.append(RadcorActivity.collection_id == args['collection'])
        if args.get('type'): filters.append(RadcorActivity.activity_type.contains(args['type']))

        result = db.session.query(Task.status, func.count('*'))\
            .join(RadcorActivityHistory, RadcorActivityHistory.task_id==Task.id)\
            .join(RadcorActivity, RadcorActivity.id==RadcorActivityHistory.activity_id)\
            .filter(*filters)\
            .group_by(Task.status)\
            .all()

        return {r[0]: r[1] for r in result}

    @classmethod
    def count_activities_with_date(cls, args: dict):
        """Count activities by date."""
        filters = []
        if args.get('start_date'): filters.append(RadcorActivityHistory.start >= '{}T00:00'.format(args['start_date']))
        if args.get('last_date'): filters.append(RadcorActivityHistory.start <= '{}T23:59'.format(args['last_date']))
        if args.get('collection'): filters.append(RadcorActivity.collection_id == args['collection'])
        if args.get('type'): filters.append(RadcorActivity.activity_type.contains(args['type']))

        result = db.session.query(RadcorActivityHistory.start.cast(Date), Task.status, func.count('*'))\
            .join(RadcorActivityHistory, RadcorActivityHistory.task_id==Task.id)\
            .join(RadcorActivity, RadcorActivity.id==RadcorActivityHistory.activity_id)\
            .filter(*filters)\
            .group_by(RadcorActivityHistory.start.cast(Date), Task.status)\
            .order_by(RadcorActivityHistory.start.cast(Date))\
            .all()

        return [{'date': r[0].strftime('%Y-%m-%d'), 'status': r[1], 'count': r[2]} for r in result]

    @classmethod
    def get_collections_activities(cls):
        """Retrieve activities distinct."""
        activities = RadcorActivity.query().distinct(RadcorActivity.collection_id).all()
        return [act.collection_id for act in activities]

    @classmethod
    def get_unsuccessfully_activities(cls):
        """Retrieve all failed activities."""
        result = db.engine.execute("\
            WITH activity_tasks AS (\
                SELECT a.sceneid AS sceneid,\
                    max(h.start) AS start_date\
                FROM activity_history h, celery_taskmeta t, activities a\
                WHERE h.task_id = t.id AND a.id = h.activity_id\
                GROUP BY 1\
            ), failed_tasks AS (\
                SELECT a.id AS id,\
                a.sceneid AS sceneid,\
                a.activity_type AS type\
                FROM activity_tasks act, activity_history h, celery_taskmeta t, activities a\
                WHERE a.sceneid = act.sceneid AND h.start = act.start_date AND a.id = h.activity_id \
                    AND t.id = h.task_id AND t.status != 'SUCCESS' ORDER BY a.id\
            ) \
            SELECT count(*) FROM failed_tasks").first()
        return {"result": result.count}
