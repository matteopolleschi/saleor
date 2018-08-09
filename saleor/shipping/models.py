from django.conf import settings
from django.db import models
from django.utils.safestring import mark_safe
from django.utils.translation import pgettext_lazy
from django_countries.fields import CountryField
from django_measurement.models import MeasurementField
from django_prices.models import MoneyField
from measurement.measures import Weight
from prices import MoneyRange

from . import ShippingMethodType
from ..core.utils import format_money
from ..shipping.utils import get_taxed_shipping_price


class ShippingZone(models.Model):
    name = models.CharField(max_length=100)
    countries = CountryField(multiple=True)

    def __str__(self):
        return self.name

    def get_countries_display(self):
        if len(self.countries) <= 3:
            return ','.join((country.name for country in self.countries))
        return pgettext_lazy(
            'Number of countries shipping zone apply to',
            '%(num_of_countries)d countries' % {
                'num_of_countries': len(self.countries)})

    @property
    def price_range(self):
        prices = [
            shipping_method.get_total_price()
            for shipping_method in self.shipping_methods.all()]
        if prices:
            return MoneyRange(min(prices).net, max(prices).net)
        return None

    class Meta:
        permissions = ((
            'manage_shipping', pgettext_lazy(
                'Permission description', 'Manage shipping.')),)


class ShippingMethodQueryset(models.QuerySet):
    def price_based(self):
        return self.filter(type=ShippingMethodType.PRICE_BASED)

    def weight_based(self):
        return self.filter(type=ShippingMethodType.WEIGHT_BASED)


class ShippingMethod(models.Model):
    name = models.CharField(max_length=100)
    type = models.CharField(
        max_length=30, choices=ShippingMethodType.CHOICES,
        default=ShippingMethodType.WEIGHT_BASED)
    price = MoneyField(
        currency=settings.DEFAULT_CURRENCY, max_digits=12,
        decimal_places=settings.DEFAULT_DECIMAL_PLACES, default=0)
    shipping_zone = models.ForeignKey(
        ShippingZone, related_name='shipping_methods',
        on_delete=models.CASCADE)
    minimum_order_price = MoneyField(
        currency=settings.DEFAULT_CURRENCY, max_digits=12,
        decimal_places=settings.DEFAULT_DECIMAL_PLACES, default=0, blank=True)
    maximum_order_price = MoneyField(
        currency=settings.DEFAULT_CURRENCY, max_digits=12,
        decimal_places=settings.DEFAULT_DECIMAL_PLACES, blank=True, null=True)
    minimum_order_weight = MeasurementField(
        measurement=Weight, unit_choices=settings.DEFAULT_WEIGHT_UNITS,
        default=0)
    maximum_order_weight = MeasurementField(
        measurement=Weight, unit_choices=settings.DEFAULT_WEIGHT_UNITS,
        blank=True, null=True)

    objects = ShippingMethodQueryset.as_manager()

    def __str__(self):
        return self.name

    def get_total_price(self, taxes=None):
        return get_taxed_shipping_price(self.price, taxes)

    def get_ajax_label(self):
        price_html = format_money(self.price)
        label = mark_safe('%s %s' % (self, price_html))
        return label

    def get_weight_type_display(self):
        if self.maximum_order_weight is None:
            return pgettext_lazy(
                'Applies to orders heavier than the threshold',
                '%(minimum_order_weight)s and up') % {
                    'minimum_order_weight': self.minimum_order_weight}
        return pgettext_lazy(
            'Applies to orders of total weight within this range',
            '%(minimum_order_weight)s to %(maximum_order_weight)s' % {
                'minimum_order_weight': self.minimum_order_weight,
                'maximum_order_weight': self.maximum_order_weight})

    def get_price_type_display(self):
        if self.maximum_order_price is None:
            return pgettext_lazy(
                'Applies to orders more expensive than the min value',
                '%(minimum_order_price)s and up') % {
                    'minimum_order_price': format_money(
                        self.minimum_order_price)}
        return pgettext_lazy(
            'Applies to order valued within this price range',
            '%(minimum_order_price)s to %(maximum_order_price)s') % {
                'minimum_order_price': format_money(self.minimum_order_price),
                'maximum_order_price': format_money(self.maximum_order_price)}

    def get_type_display(self):
        if self.type == ShippingMethodType.PRICE_BASED:
            return self.get_price_type_display()
        return self.get_weight_type_display()
