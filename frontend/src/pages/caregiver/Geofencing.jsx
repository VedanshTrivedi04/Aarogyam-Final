import React, { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { MapPin, Plus, Trash2, Shield, ShieldAlert, AlertCircle, CheckCircle2, LocateFixed, Circle as CircleIcon, Hexagon, Undo2, RotateCcw } from 'lucide-react';
import { MapContainer, TileLayer, Marker, Circle, Polygon, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { useGeofenceZones, useCreateGeofenceZone, useDeleteGeofenceZone, useGeofenceEvents } from '@/hooks/useGeofence';
import { useCaregiverPatients } from '@/hooks/useCaregiver';
import { Card, CardContent } from '@/components/ui/Card';
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

const DEFAULT_CENTER = [28.6139, 77.2090]; // fallback until geolocation resolves
const MAX_RADIUS_M = 100;
const MIN_RADIUS_M = 1;
const MAX_POINTS = 8;
const MIN_POINTS = 3;

function haversineMeters(lat1, lng1, lat2, lng2) {
  const R = 6_371_000;
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function LocationPicker({ onPick }) {
  useMapEvents({
    click(e) { onPick(e.latlng.lat, e.latlng.lng); },
  });
  return null;
}

// react-leaflet only applies center/zoom on first mount — this keeps an
// already-mounted map in sync when the target position changes later
// (geolocation resolving async, or the caregiver switching patients).
function RecenterMap({ position, zoom }) {
  const map = useMap();
  React.useEffect(() => {
    // Modals/animated containers can mount before Leaflet reads a stable
    // size for the map div — re-measure before recentering so tiles don't
    // render at a stale (often huge/blank) size.
    map.invalidateSize();
    if (position) map.setView(position, zoom ?? map.getZoom());
  }, [position, zoom, map]);
  return null;
}

const EVENT_COLORS = {
  ENTRY: { bg: 'bg-emerald-100', text: 'text-emerald-700', icon: CheckCircle2, label: 'Entered Zone' },
  EXIT:  { bg: 'bg-rose-100',    text: 'text-rose-700',    icon: ShieldAlert,  label: 'Left Zone'    },
};

function CreateZoneModal({ patientId, onClose }) {
  const createZone = useCreateGeofenceZone();
  const [label, setLabel] = useState('');
  const [shapeType, setShapeType] = useState('CIRCLE');
  const [anchor, setAnchor] = useState(null); // [lat, lng]
  const [radius, setRadius] = useState(50);
  const [points, setPoints] = useState([]); // polygon vertices, anchor included at index 0
  const [locating, setLocating] = useState(false);
  const [pointError, setPointError] = useState('');

  const handleUseMyLocation = () => {
    if (!navigator.geolocation) {
      setPointError('Geolocation is not available in this browser.');
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        setAnchor([latitude, longitude]);
        setPoints([[latitude, longitude]]);
        setLocating(false);
      },
      () => { setPointError('Could not read your location. Please allow location access, or click a point on the map instead.'); setLocating(false); },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  };

  const handleMapClick = (lat, lng) => {
    setPointError('');
    if (!anchor) {
      setAnchor([lat, lng]);
      setPoints([[lat, lng]]);
      return;
    }
    if (shapeType === 'CIRCLE') {
      setAnchor([lat, lng]);
      setPoints([[lat, lng]]);
      return;
    }
    // POLYGON: add a new vertex, constrained to <=100m of the anchor
    if (points.length >= MAX_POINTS) {
      setPointError(`You can place at most ${MAX_POINTS} points.`);
      return;
    }
    const dist = haversineMeters(anchor[0], anchor[1], lat, lng);
    if (dist > MAX_RADIUS_M) {
      setPointError(`That point is ${Math.round(dist)}m from your anchor — points must stay within ${MAX_RADIUS_M}m.`);
      return;
    }
    setPoints((prev) => [...prev, [lat, lng]]);
  };

  const handleUndoPoint = () => {
    setPointError('');
    setPoints((prev) => {
      const next = prev.slice(0, -1);
      if (next.length === 0) setAnchor(null);
      else setAnchor(next[0]);
      return next;
    });
  };

  const handleReset = () => {
    setPointError('');
    setAnchor(null);
    setPoints([]);
  };

  const handleShapeChange = (next) => {
    setShapeType(next);
    setPointError('');
    if (next === 'CIRCLE' && anchor) setPoints([anchor]);
  };

  const canSubmit = shapeType === 'CIRCLE'
    ? !!anchor
    : points.length >= MIN_POINTS;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!canSubmit || !anchor) return;

    const payload = shapeType === 'CIRCLE'
      ? {
          patient_id: patientId,
          label,
          shape_type: 'CIRCLE',
          latitude: anchor[0],
          longitude: anchor[1],
          radius_meters: radius,
        }
      : {
          patient_id: patientId,
          label,
          shape_type: 'POLYGON',
          latitude: anchor[0],
          longitude: anchor[1],
          points,
        };

    createZone.mutate(payload, { onSuccess: onClose });
  };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
        className="bg-card rounded-2xl border border-border shadow-2xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto"
      >
        <h2 className="text-xl font-bold mb-1">Create Safe Zone</h2>
        <p className="text-sm text-muted-foreground mb-4">
          Use your current location, or click anywhere else on the map to pick a different spot. Zones can be up to {MAX_RADIUS_M}m across.
        </p>

        {/* Shape toggle */}
        <div className="grid grid-cols-2 gap-2 mb-3">
          <button type="button" onClick={() => handleShapeChange('CIRCLE')}
            className={`flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-bold border-2 transition-all ${shapeType === 'CIRCLE' ? 'border-primary bg-primary/10 text-primary' : 'border-border/60 text-muted-foreground'}`}>
            <CircleIcon className="w-4 h-4" /> Circle
          </button>
          <button type="button" onClick={() => handleShapeChange('POLYGON')}
            className={`flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-bold border-2 transition-all ${shapeType === 'POLYGON' ? 'border-primary bg-primary/10 text-primary' : 'border-border/60 text-muted-foreground'}`}>
            <Hexagon className="w-4 h-4" /> Custom Shape (up to {MAX_POINTS} points)
          </button>
        </div>

        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium">
            {shapeType === 'CIRCLE' ? 'Pick a center point' : `Click up to ${MAX_POINTS} points (${points.length}/${MAX_POINTS})`}
          </span>
          <div className="flex items-center gap-3">
            {shapeType === 'POLYGON' && points.length > 0 && (
              <button type="button" onClick={handleUndoPoint} className="text-xs font-bold text-muted-foreground hover:text-foreground flex items-center gap-1">
                <Undo2 className="w-3.5 h-3.5" /> Undo
              </button>
            )}
            {anchor && (
              <button type="button" onClick={handleReset} className="text-xs font-bold text-muted-foreground hover:text-foreground flex items-center gap-1">
                <RotateCcw className="w-3.5 h-3.5" /> Reset
              </button>
            )}
            <button type="button" onClick={handleUseMyLocation} disabled={locating}
              className="text-xs font-bold text-primary hover:underline disabled:opacity-50 flex items-center gap-1">
              <LocateFixed className="w-3.5 h-3.5" /> {locating ? 'Locating…' : 'Use my current location'}
            </button>
          </div>
        </div>

        <div className="isolate relative rounded-xl overflow-hidden border border-border mb-2" style={{ height: 280 }}>
          <MapContainer center={anchor || DEFAULT_CENTER} zoom={anchor ? 17 : 11} style={{ height: '100%', width: '100%' }}>
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            />
            <LocationPicker onPick={handleMapClick} />
            <RecenterMap position={anchor} zoom={17} />
            {anchor && shapeType === 'CIRCLE' && (
              <>
                <Marker
                  position={anchor}
                  draggable
                  eventHandlers={{ dragend: (e) => { const { lat, lng } = e.target.getLatLng(); setAnchor([lat, lng]); setPoints([[lat, lng]]); } }}
                />
                <Circle center={anchor} radius={radius} pathOptions={{ color: '#0B6E7A', fillOpacity: 0.15 }} />
              </>
            )}
            {shapeType === 'POLYGON' && points.map((p, i) => (
              <Marker key={i} position={p} />
            ))}
            {shapeType === 'POLYGON' && points.length >= 3 && (
              <Polygon positions={points} pathOptions={{ color: '#0B6E7A', fillOpacity: 0.15 }} />
            )}
            {shapeType === 'POLYGON' && anchor && (
              <Circle center={anchor} radius={MAX_RADIUS_M} pathOptions={{ color: '#94a3b8', dashArray: '4 6', fill: false }} />
            )}
          </MapContainer>
        </div>

        {pointError && (
          <p className="text-xs font-semibold text-destructive mb-3 flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" /> {pointError}
          </p>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="text-sm font-medium mb-1 block">Zone Name</label>
            <input required type="text" placeholder="e.g. Home, Hospital"
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              value={label} onChange={e => setLabel(e.target.value)} />
          </div>

          {shapeType === 'CIRCLE' ? (
            <div>
              <label className="text-sm font-medium mb-1 block">Radius (meters)</label>
              <input type="range" min={MIN_RADIUS_M} max={MAX_RADIUS_M} step={1}
                className="w-full"
                value={radius} onChange={e => setRadius(Number(e.target.value))} />
              <div className="flex items-center justify-between mt-1">
                <p className="text-xs text-muted-foreground">No minimum, up to {MAX_RADIUS_M}m. Drag the marker or click the map to move it.</p>
                <span className="text-xs font-bold text-primary">{radius}m</span>
              </div>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              Need at least {MIN_POINTS} points to form a shape. Every point must stay within the dashed {MAX_RADIUS_M}m guide circle around your first point.
            </p>
          )}

          <div className="flex gap-3 pt-2">
            <Button type="button" variant="outline" className="flex-1" onClick={onClose}>Cancel</Button>
            <Button type="submit" className="flex-1" disabled={createZone.isPending || !canSubmit}>
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
  const { data: patients = [], isLoading: patientsLoading } = useCaregiverPatients();
  const [explicitPatientId, setExplicitPatientId] = useState('');
  const selectedPatientId = explicitPatientId || patients[0]?.id || '';

  const { data: zones = [], isLoading: zonesLoading } = useGeofenceZones(selectedPatientId);
  const { data: events = [], isLoading: eventsLoading } = useGeofenceEvents({ patient_id: selectedPatientId, limit: 20 });
  const deleteZone = useDeleteGeofenceZone();

  const mapCenter = useMemo(() => {
    if (!zones.length) return DEFAULT_CENTER;
    return [parseFloat(zones[0].latitude), parseFloat(zones[0].longitude)];
  }, [zones]);

  return (
    <div className="flex flex-col gap-8 py-4 max-w-[1600px] mx-auto w-full">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-display font-bold text-foreground">Geofencing</h1>
          <p className="text-muted-foreground mt-1">Define safe zones and get alerted when patients leave them.</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={selectedPatientId}
            onChange={(e) => setExplicitPatientId(e.target.value)}
            disabled={patientsLoading || !patients.length}
            className="h-11 rounded-xl border border-border bg-background px-3 text-sm font-bold min-w-[180px]"
          >
            {!patients.length && <option value="">No linked patients</option>}
            {patients.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <Button onClick={() => setShowCreate(true)} className="gap-2" disabled={!selectedPatientId}>
            <Plus className="w-4 h-4" /> Add Zone
          </Button>
        </div>
      </div>

      {!zonesLoading && zones.length > 0 && (
        <div className="isolate relative rounded-2xl overflow-hidden border border-border" style={{ height: 320 }}>
          <MapContainer center={mapCenter} zoom={16} style={{ height: '100%', width: '100%' }}>
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            />
            <RecenterMap position={mapCenter} zoom={16} />
            {zones.map((zone, i) => {
              const pos = [parseFloat(zone.latitude), parseFloat(zone.longitude)];
              const color = zone.is_active ? '#0B6E7A' : '#94a3b8';
              return (
                <React.Fragment key={zone.id || i}>
                  <Marker position={pos} />
                  {zone.shape_type === 'POLYGON' && zone.points?.length >= 3 ? (
                    <Polygon positions={zone.points} pathOptions={{ color, fillOpacity: 0.15 }} />
                  ) : (
                    <Circle center={pos} radius={zone.radius_meters} pathOptions={{ color, fillOpacity: 0.15 }} />
                  )}
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

          {!selectedPatientId ? (
            <div className="py-10 text-center border-2 border-dashed border-border/50 rounded-2xl bg-card">
              <MapPin className="w-10 h-10 text-muted-foreground/20 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">Link a patient first to set up geofencing.</p>
            </div>
          ) : zonesLoading ? (
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
                        {zone.shape_type === 'POLYGON' ? <Hexagon className="w-5 h-5" /> : <MapPin className="w-5 h-5" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <h4 className="font-bold text-sm truncate">{zone.label}</h4>
                        <p className="text-xs text-muted-foreground">
                          {zone.shape_type === 'POLYGON' ? `Custom shape · ${zone.points?.length || 0} points` : `${zone.radius_meters}m radius`}
                        </p>
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
                            {ev.zone_label && <span className="text-foreground"> · {ev.zone_label}</span>}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {ev.patient_name && <span>{ev.patient_name} · </span>}
                            {new Date(ev.triggered_at).toLocaleString()}
                          </p>
                        </div>
                        <Badge variant={ev.event_type === 'ENTRY' ? 'success' : 'danger'}>
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

      {showCreate && <CreateZoneModal patientId={selectedPatientId} onClose={() => setShowCreate(false)} />}
    </div>
  );
}
