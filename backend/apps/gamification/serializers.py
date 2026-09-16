from rest_framework import serializers
from .models import Streak, Badge, WeeklyAdherenceScore

class StreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = Streak
        fields = ['id', 'patient', 'current_days', 'longest_days', 'last_dose_date']
        read_only_fields = ['id', 'patient', 'current_days', 'longest_days', 'last_dose_date']


# Display metadata for each badge type — the model only stores the type key,
# this is the presentation layer the frontend actually renders.
BADGE_META = {
    'FIRST_DOSE':          {'name': 'First Dose',        'description': 'Took your first medication dose',  'icon': '🎉'},
    '7_DAY_STREAK':        {'name': 'Week Warrior',       'description': '7 days in a row',                  'icon': '🔥'},
    '14_DAY_STREAK':       {'name': 'Two-Week Titan',     'description': '14 days in a row',                 'icon': '🔥'},
    '30_DAY_STREAK':       {'name': 'Monthly Master',     'description': '30 days in a row',                 'icon': '🏆'},
    '60_DAY_STREAK':       {'name': '60-Day Champion',    'description': '60 days in a row',                 'icon': '🥇'},
    '90_DAY_STREAK':       {'name': 'Quarter Legend',     'description': '90 days in a row',                 'icon': '💎'},
    '180_DAY_STREAK':      {'name': 'Half-Year Hero',     'description': '180 days in a row',                'icon': '👑'},
    '365_DAY_STREAK':      {'name': 'Year-Long Legend',   'description': '365 days in a row',                'icon': '🌟'},
    'PERFECT_WEEK':        {'name': 'Perfect Week',       'description': 'Every dose taken this week',       'icon': '🌈'},
    'PERFECT_MONTH':       {'name': 'Perfect Month',      'description': 'Every dose taken this month',      'icon': '🎯'},
    'DEVICE_LINKED':       {'name': 'Smart Start',        'description': 'Linked your smart dispenser',      'icon': '📱'},
    'ABHA_LINKED':         {'name': 'Digitally Connected','description': 'Linked your ABHA health ID',       'icon': '🆔'},
    'DIGITAL_RX':          {'name': 'Prescribed Digitally','description': 'Received a digital prescription', 'icon': '📋'},
    'REFILL_PROACTIVE':    {'name': 'Refill Pro',         'description': 'Reordered before running out',     'icon': '📦'},
    'CAREGIVER_HERO':      {'name': 'Caregiver Hero',     'description': 'A caregiver went above and beyond','icon': '🦸'},
    'WHATSAPP_ONBOARDED':  {'name': 'Connected',          'description': 'Onboarded via WhatsApp',           'icon': '💬'},
}
_DEFAULT_BADGE_META = {'name': 'Badge', 'description': '', 'icon': '🏅'}


class BadgeSerializer(serializers.ModelSerializer):
    badge_type_display = serializers.CharField(source='get_badge_type_display', read_only=True)
    name        = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    icon        = serializers.SerializerMethodField()

    class Meta:
        model = Badge
        fields = ['id', 'patient', 'badge_type', 'badge_type_display', 'name', 'description', 'icon', 'earned_at']
        read_only_fields = ['id', 'patient', 'earned_at']

    def _meta(self, obj):
        return BADGE_META.get(obj.badge_type, _DEFAULT_BADGE_META)

    def get_name(self, obj):
        return self._meta(obj)['name']

    def get_description(self, obj):
        return self._meta(obj)['description']

    def get_icon(self, obj):
        return self._meta(obj)['icon']


class WeeklyAdherenceScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklyAdherenceScore
        fields = ['id', 'patient', 'week_start', 'score', 'total_doses', 'taken_doses', 'missed_doses']
        read_only_fields = ['id', 'patient', 'week_start', 'score', 'total_doses', 'taken_doses', 'missed_doses']
