import React, { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { MapPin, Plus, Trash2, Shield, ShieldAlert, AlertCircle, CheckCircle2 } from 'lucide-react';
import { MapContainer, TileLayer, Marker, Circle, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useGeofenceZones, useCreateGeofenceZone, useDeleteGeofenceZone, useGeofenceEvents } from '@/hooks/useGeofence';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';

// Leaflet's default marker icons reference bundler-relative asset paths that break under Vite —
// point them at the CDN copies that ship in the same package version instead.
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const DEFAULT_CENTER = [28.6139, 77.2090]; // New Delhi fallback

function LocationPicker({ onPick }) {
  useMapEvents({
    click(e) {
      onPick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

const EVENT_COLORS = {
  ENTER: { bg: 'bg-emerald-100', text: 'text-emerald-700', icon: CheckCircle2, label: 'Entered Zone' },
  EXIT:  { bg: 'bg-rose-100',    text: 'text-rose-700',    icon: ShieldAlert,  label: 'Left Zone'    },
};

function CreateZoneModal({ onClose }) {
  const createZone = useCreateGeofenceZone();
  const [form, setForm] = useState({ name: '', latitude: '', longitude: '', radius_meters: 200 });
  const [locating, setLocating] = useState(false);

  const hasPoint = form.latitude !== '' && form.longitude !== '';
  const markerPos = hasPoint ? [parseFloat(form.latitude), parseFloat(form.longitude)] : null;

  const handlePick = (lat, lng) => {
    setForm(f => ({ ...f, latitude: lat.toFixed(6), longitude: lng.toFixed(6) }));
  };

  const handleUseMyLocation = () => {
    if (!navigator.geolocation) return;
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        handlePick(pos.coords.latitude, pos.coords.longitude);
        setLocating(false);
      },
      () => setLocating(false),
      { enableHighAccuracy: true, timeout: 8000 }
    );
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    createZone.mutate({
      name: form.name,
      latitude: parseFloat(form.latitude),
      longitude: parseFloat(form.longitude),
      radius_meters: parseInt(form.radius_meters),
    }, { onSuccess: onClose });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
        className="bg-card rounded-2xl border border-border shadow-2xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto"
      >
        <h2 className="text-xl font-bold mb-1">Create Safe Zone</h2>
        <p className="text-sm text-muted-foreground mb-4">Click anywhere on the map to drop a pin, or use your current location. Drag the radius handle below to size the zone.</p>

        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium">Pick a location</span>
          <button type="button" onClick={handleUseMyLocation} disabled={locating}
            className="text-xs font-bold text-primary hover:underline disabled:opacity-50">
            {locating ? 'Locating…' : 'Use my current location'}
          </button>
        </div>

        <div className="rounded-xl overflow-hidden border border-border mb-4" style={{ height: 260 }}>
          <MapContainer center={markerPos || DEFAULT_CENTER} zoom={markerPos ? 15 : 11} style={{ height: '100%', width: '100%' }}>
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            />
            <LocationPicker onPick={handlePick} />
            {markerPos && (
              <>
                <Marker
                  position={markerPos}
                  draggable
                  eventHandlers={{ dragend: (e) => { const { lat, lng } = e.target.getLatLng(); handlePick(lat, lng); } }}
                />
                <Circle center={markerPos} radius={Number(form.radius_meters) || 200} pathOptions={{ color: '#0B6E7A', fillOpacity: 0.15 }} />
              </>
            )}
          </MapContainer>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="text-sm font-medium mb-1 block">Zone Name</label>
            <input required type="text" placeholder="e.g. Home, Hospital"
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium mb-1 block">Latitude</label>
              <input required type="number" step="any" placeholder="28.6139"
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                value={form.latitude} onChange={e => setForm(f => ({ ...f, latitude: e.target.value }))} />
            </div>
            <div>
              <label className="text-sm font-medium mb-1 block">Longitude</label>
              <input required type="number" step="any" placeholder="77.2090"
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                value={form.longitude} onChange={e => setForm(f => ({ ...f, longitude: e.target.value }))} />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium mb-1 block">Radius (meters)</label>
            <input type="range" min={50} max={5000} step={10}
              className="w-full"
              value={form.radius_meters} onChange={e => setForm(f => ({ ...f, radius_meters: e.target.value }))} />
            <div className="flex items-center justify-between mt-1">
              <p className="text-xs text-muted-foreground">Minimum 50m. Drag to resize the circle on the map.</p>
              <span className="text-xs font-bold text-primary">{form.radius_meters}m</span>
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <Button type="button" variant="outline" className="flex-1" onClick={onClose}>Cancel</Button>
            <Button type="submit" className="flex-1" disabled={createZone.isPending || !hasPoint}>
              {createZone.isPending ? 'Creating…' : 'Create Zone'}
            </Button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}

export default function Geofencing() {
  const [showCreate, setShowCreate] = useState(false);
  const { data: zones = [], isLoading: zonesLoading } = useGeofenceZones();
  const { data: events = [], isLoading: eventsLoading } = useGeofenceEvents({ limit: 20 });
  const deleteZone = useDeleteGeofenceZone();

  const mapCenter = useMemo(() => {
    if (!zones.length) return DEFAULT_CENTER;
    return [parseFloat(zones[0].latitude), parseFloat(zones[0].longitude)];
  }, [zones]);

  return (
    <div className="flex flex-col gap-8 py-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-foreground">Geofencing</h1>
          <p className="text-muted-foreground mt-1">Define safe zones and get alerted when patients leave them.</p>
        </div>
        <Button onClick={() => setShowCreate(true)} className="gap-2">
          <Plus className="w-4 h-4" /> Add Zone
        </Button>
      </div>

      {!zonesLoading && zones.length > 0 && (
        <div className="rounded-2xl overflow-hidden border border-border" style={{ height: 320 }}>
          <MapContainer center={mapCenter} zoom={12} style={{ height: '100%', width: '100%' }}>
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            />
            {zones.map((zone, i) => {
              const pos = [parseFloat(zone.latitude), parseFloat(zone.longitude)];
              return (
                <React.Fragment key={zone.id || i}>
                  <Marker position={pos} />
                  <Circle center={pos} radius={zone.radius_meters} pathOptions={{ color: zone.is_active ? '#0B6E7A' : '#94a3b8', fillOpacity: 0.15 }} />
                </React.Fragment>
              );
            })}
          </MapContainer>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        {/* Safe Zones list */}
        <div className="xl:col-span-1 flex flex-col gap-4">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <Shield className="w-5 h-5 text-primary" /> Safe Zones
          </h2>

          {zonesLoading ? (
            <div className="flex flex-col gap-3">
              {[1, 2].map(i => <Card key={i} className="h-24 animate-pulse bg-muted/40 border-0" />)}
            </div>
          ) : zones.length === 0 ? (
            <div className="py-10 text-center border-2 border-dashed border-border/50 rounded-2xl bg-card">
              <MapPin className="w-10 h-10 text-muted-foreground/20 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">No safe zones yet.<br />Add one to start monitoring.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {zones.map((zone, i) => (
                <motion.div key={zone.id || i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.06 }}>
                  <Card className="border-border/50 hover:border-primary/30 transition-colors group">
                    <CardContent className="p-4 flex items-center gap-4">
                      <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary shrink-0">
                        <MapPin className="w-5 h-5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h4 className="font-bold text-sm truncate">{zone.name}</h4>
                        <p className="text-xs text-muted-foreground">{zone.radius_meters}m radius</p>
                        <p className="text-xs text-muted-foreground font-mono">
                          {parseFloat(zone.latitude).toFixed(4)}, {parseFloat(zone.longitude).toFixed(4)}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <Badge variant={zone.is_active ? 'success' : 'secondary'} className="text-xs">
                          {zone.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                        <button
                          onClick={() => deleteZone.mutate(zone.id)}
                          className="opacity-0 group-hover:opacity-100 transition-opacity text-destructive hover:text-destructive/80"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              ))}
            </div>
          )}
        </div>

        {/* Breach Events */}
        <div className="xl:col-span-2 flex flex-col gap-4">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-destructive" /> Recent Events
          </h2>

          <Card>
            <CardContent className="p-0">
              {eventsLoading ? (
                <div className="p-6 text-center text-muted-foreground">Loading events…</div>
              ) : events.length === 0 ? (
                <div className="py-16 text-center text-muted-foreground">
                  <CheckCircle2 className="w-12 h-12 text-emerald-500/30 mx-auto mb-3" />
                  <p className="font-semibold">All Clear</p>
                  <p className="text-sm mt-1">No geofence breaches recorded.</p>
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {events.map((ev, i) => {
                    const meta = EVENT_COLORS[ev.event_type] || EVENT_COLORS.EXIT;
                    const EventIcon = meta.icon;
                    return (
                      <motion.div
                        key={ev.id || i}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: i * 0.04 }}
                        className="flex items-center gap-4 p-4 hover:bg-muted/30 transition-colors"
                      >
                        <div className={`w-10 h-10 rounded-xl ${meta.bg} flex items-center justify-center shrink-0`}>
                          <EventIcon className={`w-5 h-5 ${meta.text}`} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-sm">
                            <span className={meta.text}>{meta.label}</span>
                            {ev.zone_name && <span className="text-foreground"> · {ev.zone_name}</span>}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {ev.patient_name && <span>{ev.patient_name} · </span>}
                            {new Date(ev.created_at || ev.timestamp).toLocaleString()}
                          </p>
                        </div>
                        <Badge variant={ev.event_type === 'ENTER' ? 'success' : 'danger'}>
                          {ev.event_type}
                        </Badge>
                      </motion.div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {showCreate && <CreateZoneModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}
