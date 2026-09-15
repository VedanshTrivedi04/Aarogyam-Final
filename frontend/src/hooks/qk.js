export const STALE = {
  TODAY_SCHEDULE:    30  * 1000,        // 30 seconds
  ADHERENCE_RATE:    60  * 1000,        // 1 minute
  RISK_SCORE:        2   * 60 * 1000,   // 2 minutes
  AI_INSIGHTS:       5   * 60 * 1000,   // 5 minutes
  AGENT_ACTIVITY:    5   * 60 * 1000,   // 5 minutes
  SUBSCRIPTION:      10  * 60 * 1000,   // 10 minutes
  USER_PROFILE:      15  * 60 * 1000,   // 15 minutes
  CAREGIVER_ALERTS:  15  * 60 * 1000,   // 15 minutes
  MEDICATION_LIST:   30  * 60 * 1000,   // 30 minutes
  PLAN_LIST:         60  * 60 * 1000,   // 1 hour
  STORE_PRODUCTS:    60  * 60 * 1000,   // 1 hour
};

export const qk = {
  // Auth
  auth: {
    me:       ()         => ['auth', 'me'],
    sessions: ()         => ['auth', 'sessions'],
  },

  // Patient
  patient: {
    profile:    ()        => ['patient', 'profile'],
    conditions: ()        => ['patient', 'conditions'],
    consents:   ()        => ['patient', 'consents'],
  },

  // Medications
  medication: {
    all:        ()        => ['medication', 'list'],
    detail:     (id)      => ['medication', 'detail', id],
    search:     (q)       => ['medication', 'search', q],
    digitalRx:  ()        => ['medication', 'digital-rx'],
    interactions: (ids)   => ['medication', 'interactions', ids.sort().join(',')],
  },

  // Adherence
  adherence: {
    today:      (pid)     => ['adherence', 'today', pid ?? 'me'],
    history:    (pid, f)  => ['adherence', 'history', pid ?? 'me', f],
    rate:       (pid)     => ['adherence', 'rate', pid ?? 'me'],
    heatmap:    (pid)     => ['adherence', 'heatmap', pid ?? 'me'],
    streak:     (pid)     => ['adherence', 'streak', pid ?? 'me'],
  },

  // AI
  ai: {
    riskScore:  (pid)     => ['ai', 'risk', pid ?? 'me'],
    insights:   (pid)     => ['ai', 'insights', pid ?? 'me'],
    patterns:   (pid)     => ['ai', 'patterns', pid ?? 'me'],
    rateInsight:(pid)     => ['ai', 'rate-insight', pid ?? 'me'],
    agentActivity: (pid)  => ['ai', 'agent-activity', pid ?? 'me'],
  },

  // IoT
  iot: {
    devices:    ()        => ['iot', 'devices'],
    device:     (id)      => ['iot', 'device', id],
    dispenserCompartments: (id) => ['iot', 'dispenser-compartments', id],
    compartments: (id)    => ['iot', 'compartments', id],
    inventory:  (id)      => ['iot', 'device', id, 'inventory'],
    events:     (id)      => ['iot', 'events', id],
  },

  // Notifications
  notification: {
    preferences: ()       => ['notification', 'preferences'],
    history:    (page)    => ['notification', 'history', page],
  },

  // Caregiver
  caregiver: {
    patients:   ()        => ['caregiver', 'patients'],
    patient:    (id)      => ['caregiver', 'patient', id],
    schedule:   (id)      => ['caregiver', 'schedule', id],
    adherence:  (id)      => ['caregiver', 'adherence', id],
    vitals:     (id)      => ['caregiver', 'vitals', id],
    alerts:     ()        => ['caregiver', 'alerts'],
    myCaregivers: ()      => ['patient', 'caregivers'],
    invites:    ()        => ['patient', 'caregiver-invites'],
  },

  // Subscription & Store
  subscription: {
    plans:      ()        => ['subscription', 'plans'],
    current:    (uid)     => ['subscription', 'current', uid],
    invoices:   ()        => ['subscription', 'invoices'],
  },
  store: {
    products:   (filters) => ['store', 'products', filters],
    product:    (id)      => ['store', 'product', id],
    orders:     ()        => ['store', 'orders'],
    order:      (id)      => ['store', 'order', id],
  },

  // Vitals
  vitals: {
    all:        ()        => ['vitals', 'all'],
    history:    (type)    => ['vitals', 'history', type],
    targets:    ()        => ['vitals', 'targets'],
  },

  // Gamification
  gamification: {
    badges:     ()        => ['gamification', 'badges'],
    score:      ()        => ['gamification', 'score'],
    leaderboard: ()       => ['gamification', 'leaderboard'],
  },

  // Doctor
  doctor: {
    patients:   ()        => ['doctor', 'patients'],
    patient:    (id)      => ['doctor', 'patient', id],
    adherence:  (id)      => ['doctor', 'adherence', id],
    alerts:     (id)      => ['doctor', 'alerts', id],
    profile:    ()        => ['doctor', 'profile'],
  },

  // Admin
  admin: {
    overview:   ()        => ['admin', 'overview'],
    users:      (f)       => ['admin', 'users', f],
    user:       (id)      => ['admin', 'user', id],
    deviceIds:  (f)       => ['admin', 'device-ids', f],
    orders:     (f)       => ['admin', 'orders', f],
    analytics:  (f)       => ['admin', 'analytics', f],
    aiModels:   ()        => ['admin', 'ai-models'],
    highRisk:   ()        => ['admin', 'high-risk'],
    auditLogs:  (f)       => ['admin', 'audit-logs', f],
    health:     ()        => ['admin', 'health'],
    tenants:    ()        => ['admin', 'tenants'],
    pharmaco:   ()        => ['admin', 'pharmacovig'],
    pharmacy:   ()        => ['admin', 'pharmacy-partners'],
    notifStats: ()        => ['admin', 'notif-stats'],
    subscriptions: (f)    => ['admin', 'subscriptions', f],
  },
};
