import datetime

from django.core.management import call_command

from unittest import mock

from olympia import amo
from olympia.amo.tests import TestCase
from olympia.stats import cron
from olympia.stats.models import DownloadCount, UpdateCount


@mock.patch('olympia.stats.management.commands.index_stats.group')
class TestIndexStats(TestCase):
    fixtures = ['stats/test_models']

    def setUp(self):
        super(TestIndexStats, self).setUp()
        self.downloads = (DownloadCount.objects.order_by('-date')
                          .values_list('id', flat=True))
        self.updates = (UpdateCount.objects.order_by('-date')
                        .values_list('id', flat=True))

    def test_by_date(self, group_mock):
        call_command('index_stats', addons=None, date='2009-06-01')
        qs = self.downloads.filter(date='2009-06-01')
        download_group = group_mock.call_args[0][0][1]
        assert len(download_group) == 1
        task = download_group.tasks[0]
        assert task.task == 'olympia.stats.tasks.index_download_counts'
        assert task.args == (list(qs), None)

    def test_called_three(self, group_mock):
        call_command('index_stats', addons=None, date='2009-06-01')
        assert len(group_mock.call_args[0][0]) == 2

    def test_called_three_with_addons_param(self, group_mock):
        call_command('index_stats', addons='5', date='2009-06-01')
        assert len(group_mock.call_args[0][0]) == 2

    def test_by_date_range(self, group_mock):
        call_command('index_stats', addons=None,
                     date='2009-06-01:2009-06-07')
        qs = self.downloads.filter(date__range=('2009-06-01', '2009-06-07'))
        download_group = group_mock.call_args[0][0][1]
        assert len(download_group) == 1
        task = download_group.tasks[0]
        assert task.task == 'olympia.stats.tasks.index_download_counts'
        assert task.args == (list(qs), None)

    def test_by_addon(self, group_mock):
        call_command('index_stats', addons='5', date=None)
        qs = self.downloads.filter(addon=5)
        download_group = group_mock.call_args[0][0][1]
        assert len(download_group) == 1
        task = download_group.tasks[0]
        assert task.task == 'olympia.stats.tasks.index_download_counts'
        assert task.args == (list(qs), None)

    def test_by_addon_and_date(self, group_mock):
        call_command('index_stats', addons='4', date='2009-06-01')
        qs = self.downloads.filter(addon=4, date='2009-06-01')
        download_group = group_mock.call_args[0][0][1]
        assert len(download_group) == 1
        task = download_group.tasks[0]
        assert task.task == 'olympia.stats.tasks.index_download_counts'
        assert task.args == (list(qs), None)

    def test_multiple_addons_and_date(self, group_mock):
        call_command('index_stats', addons='4, 5', date='2009-10-03')
        qs = self.downloads.filter(addon__in=[4, 5], date='2009-10-03')
        download_group = group_mock.call_args[0][0][1]
        assert len(download_group) == 1
        task = download_group.tasks[0]
        assert task.task == 'olympia.stats.tasks.index_download_counts'
        assert task.args == (list(qs), None)

    def test_no_addon_or_date(self, group_mock):
        call_command('index_stats', addons=None, date=None)
        calls = group_mock.call_args[0][0]

        # There should be 3 updates, but 2 of them have a date close enough
        # together that they'll be indexed in the same chunk, so we should have
        # 2 calls.
        update_counts_calls = [
            c.tasks[0].args for c in calls
            if c.tasks[0].task == 'olympia.stats.tasks.index_update_counts'
        ]
        assert len(update_counts_calls) == 2

        # There should be 10 downloads, but 2 of them have a date close enough
        # together that they'll be indexed in the same chunk, so we should have
        # 9 calls.
        download_counts_calls = [
            c.tasks[0].args for c in calls
            if c.tasks[0].task == 'olympia.stats.tasks.index_download_counts'
        ]
        assert len(download_counts_calls) == 9


class TestIndexLatest(amo.tests.ESTestCase):

    def test_index_latest(self):
        self.create_switch('local-statistics-processing')
        latest = datetime.date.today() - datetime.timedelta(days=5)
        UpdateCount.index({'date': latest})
        self.refresh('stats')

        start = latest.strftime('%Y-%m-%d')
        finish = datetime.date.today().strftime('%Y-%m-%d')
        with mock.patch('olympia.stats.cron.call_command') as call:
            cron.index_latest_stats()
            call.assert_called_with('index_stats', addons=None,
                                    date='%s:%s' % (start, finish))
