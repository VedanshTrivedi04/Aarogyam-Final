import { AgentBase } from './base.agent';
import { axiosInstance as api } from '@/lib/axios';

const ADHERENCE_BASE = '/adherence';
const REMINDERS_BASE = '/reminders';

class AdherenceAgent extends AgentBase {
  async getTodaySchedule(patientId) {
    // Backend supports `/reminders/today/` for current user.
    // Caregiver view will need specialized routes later if not supported.
    const url = patientId ? `/caregivers/patients/${patientId}/reminders/today/` : `${REMINDERS_BASE}/today/`;
    return this._get(api.get(url));
  }

  async getUpcomingReminders({ days = 7, patientId } = {}) {
    const url = patientId ? `/caregivers/patients/${patientId}/reminders/upcoming/` : `${REMINDERS_BASE}/upcoming/`;
    return this._get(api.get(url, { params: { days } }));
  }

  async logDose(data) {
    // data: { reminderId, status, takenAt, source, notes }
    const { reminderId, ...payload } = data;
    // Call the specific reminder's log endpoint
    return this._post(api.post(`${REMINDERS_BASE}/${reminderId}/log/`, payload));
  }

  async dispenseNow(reminderId) {
    return this._post(api.post(`${REMINDERS_BASE}/${reminderId}/dispense-now/`));
  }

  async snoozeReminder(reminderId, minutes = 10) {
    return this._post(api.post(`${REMINDERS_BASE}/${reminderId}/snooze/`, { minutes }));
  }

  async logManualDose(data) {
    return this._post(api.post(`${ADHERENCE_BASE}/manual/`, data));
  }

  async getAdherenceRate({ days = 30, patientId } = {}) {
    const url = patientId ? `/caregivers/patients/${patientId}/adherence/summary/` : `${ADHERENCE_BASE}/summary/`;
    const res = await this._get(api.get(url, { params: { days } }));
    // Wrap in { summary } so callers access adherenceData?.summary?.adherence_pct
    return { summary: res };
  }

  async getStreak(patientId) {
    const url = patientId ? `/caregivers/patients/${patientId}/gamification/summary/` : `/gamification/summary/`;
    try {
      const res = await this._get(api.get(url));
      // Backend returns { streak: { current_days, longest_days } }
      const streak = res?.streak ?? {};
      return {
        current_streak: streak.current_days ?? 0,
        longest_streak: streak.longest_days ?? 0,
        recent_badges:  res?.recent_badges ?? [],
      };
    } catch {
      return { current_streak: 0, longest_streak: 0, recent_badges: [] };
    }
  }

  async getHeatmap({ weeks = 16, patientId } = {}) {
    const days = weeks * 7;
    const url = patientId ? `/caregivers/patients/${patientId}/adherence/timeline/` : `${ADHERENCE_BASE}/timeline/`;
    return this._get(api.get(url, { params: { days } }));
  }

  async exportReport({ startDate, endDate, format = 'pdf', patientId }) {
    const url = patientId ? `/caregivers/patients/${patientId}/adherence/export/` : `${ADHERENCE_BASE}/export/`;
    const res = await api.get(url, {
      params: { start_date: startDate, end_date: endDate, format },
      responseType: 'blob'
    });
    return res.data;
  }
}

export const adherenceAgent = new AdherenceAgent();
