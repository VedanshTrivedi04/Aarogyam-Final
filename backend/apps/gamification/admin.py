from django.contrib import admin
from .models import Streak, Badge, WeeklyAdherenceScore


@admin.register(Streak)
class StreakAdmin(admin.ModelAdmin):
    list_display = ('patient', 'current_days', 'longest_days', 'last_dose_date', 'last_broken_at')
    search_fields = ('patient__user__full_name', 'patient__user__email')


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('patient', 'badge_type', 'earned_at')
    list_filter = ('badge_type',)
    search_fields = ('patient__user__full_name', 'patient__user__email')


@admin.register(WeeklyAdherenceScore)
class WeeklyAdherenceScoreAdmin(admin.ModelAdmin):
    list_display = ('patient', 'week_start', 'score', 'taken_doses', 'total_doses')
    list_filter = ('week_start',)
    search_fields = ('patient__user__full_name', 'patient__user__email')
