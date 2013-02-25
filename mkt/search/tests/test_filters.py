import json

import test_utils
from nose.tools import eq_, ok_

from django.contrib.auth.models import AnonymousUser

import amo
from addons.models import Category
from mkt.api.tests.test_oauth import BaseOAuth
from mkt.search.forms import ApiSearchForm, DEVICE_CHOICES_IDS
from mkt.search.views import _filter_search
from mkt.site.fixtures import fixture
from mkt.webapps.models import Webapp


class TestSearchFilters(BaseOAuth):
    fixtures = fixture('webapp_337141', 'user_2519')

    def setUp(self):
        super(TestSearchFilters, self).setUp()
        self.req = test_utils.RequestFactory().get('/')
        self.req.user = AnonymousUser()

        self.category = Category.objects.create(name='games',
                                                type=amo.ADDON_WEBAPP)

    def _grant(self, rules):
        self.grant_permission(self.profile, rules)
        self.req.groups = self.profile.groups.all()

    def _filter(self, req, filters, sorting=None):
        form = ApiSearchForm(filters)
        if form.is_valid():
            qs = Webapp.from_search().facet('category')
            return _filter_search(
                self.req, qs, form.cleaned_data, sorting)._build_query()
        else:
            return form.errors.copy()

    def test_category(self):
        qs = self._filter(self.req, {'cat': self.category.pk})
        eq_(qs['filter']['term'], {'category': self.category.pk})

    def test_q(self):
        qs = self._filter(self.req, {'q': 'search terms'})
        qs_str = json.dumps(qs)
        ok_('"query": "search terms"' in qs_str)
        # TODO: Could do more checking here.

    def test_device(self):
        qs = self._filter(self.req, {'device': 'desktop'})
        eq_(qs['filter']['term'], {'device': DEVICE_CHOICES_IDS['desktop']})

    def test_premium_types(self):
        ptype = lambda p: amo.ADDON_PREMIUM_API_LOOKUP.get(p)
        # Test a single premium type.
        qs = self._filter(self.req, {'premium_types': ['free']})
        eq_(qs['filter']['in'], {'premium_type': [ptype('free')]})
        # Test many premium types.
        qs = self._filter(self.req, {'premium_types': ['free', 'free-inapp']})
        eq_(qs['filter']['in'],
            {'premium_type': [ptype('free'), ptype('free-inapp')]})
        # Test a non-existent premium type.
        qs = self._filter(self.req, {'premium_types': ['free', 'platinum']})
        ok_(u'Select a valid choice' in qs['premium_types'][0])

    def test_app_type_anonymous(self):
        # For anonymous users this has no effect.
        qs = self._filter(self.req, {'app_type': 'hosted'})
        ok_('filter' not in qs)

    def test_app_type_user(self):
        self.req.user = self.profile
        qs = self._filter(self.req, {'app_type': 'hosted'})
        ok_('filter' not in qs)

    def test_app_type_reviewer(self):
        self._grant('Apps:Review')
        self.req.user = self.profile
        qs = self._filter(self.req, {'app_type': 'hosted'})
        eq_(qs['filter']['term'], {'app_type': 1})
