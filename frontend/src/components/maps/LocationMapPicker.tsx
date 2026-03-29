import L from "leaflet";
import { useCallback, useEffect, useState } from "react";
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from "react-leaflet";
import { useTranslation } from "react-i18next";
import { ensureLeafletDefaultIcon } from "../../lib/leafletDefaultIcon";
import "leaflet/dist/leaflet.css";

ensureLeafletDefaultIcon();

export const DEFAULT_MAP_CENTER = { lat: 1.3521, lng: 103.8198 };

type Props = {
  latitude: number;
  longitude: number;
  onChange: (coords: { lat: number; lng: number }) => void;
  /** Visual theme for chrome around the map */
  lightMode?: boolean;
  /** CSS height of the map pane, e.g. "240px" */
  height?: string;
  className?: string;
  /** When false, hides “Use my current location” (e.g. worker GPS only in Settings). Default true. */
  showGeolocationButton?: boolean;
};

function MapEvents({
  onMapClick,
}: {
  onMapClick: (lat: number, lng: number) => void;
}) {
  useMapEvents({
    click(e) {
      onMapClick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

/** When parent updates coordinates (e.g. profile load), pan without changing zoom. */
function SyncView({ latitude, longitude }: { latitude: number; longitude: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView([latitude, longitude], map.getZoom(), { animate: false });
  }, [latitude, longitude, map]);
  return null;
}

/** Leaflet measures the container on init; flex/hidden parents often need a delayed invalidateSize. */
function MapLayoutFix() {
  const map = useMap();
  useEffect(() => {
    const run = () => map.invalidateSize({ animate: false });
    run();
    const id = requestAnimationFrame(run);
    const t1 = window.setTimeout(run, 100);
    const t2 = window.setTimeout(run, 400);
    return () => {
      cancelAnimationFrame(id);
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
  }, [map]);
  return null;
}

export function LocationMapPicker({
  latitude,
  longitude,
  onChange,
  lightMode = false,
  height = "240px",
  className = "",
  showGeolocationButton = true,
}: Props) {
  const { t } = useTranslation();
  const [geoMsg, setGeoMsg] = useState<string | null>(null);

  const onMapClick = useCallback(
    (lat: number, lng: number) => {
      setGeoMsg(null);
      onChange({ lat, lng });
    },
    [onChange],
  );

  const useMyLocation = useCallback(() => {
    setGeoMsg(null);
    if (!navigator.geolocation) {
      setGeoMsg(t("map_geo_unavailable"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        onChange({ lat, lng });
      },
      (err) => {
        if (err.code === err.PERMISSION_DENIED) setGeoMsg(t("map_geo_denied"));
        else setGeoMsg(t("map_geo_error"));
      },
      { enableHighAccuracy: true, timeout: 12_000, maximumAge: 60_000 },
    );
  }, [onChange, t]);

  const btnClass = lightMode
    ? "rounded-lg border border-outline-variant/40 bg-surface-container-high px-3 py-2 text-sm font-medium text-on-surface hover:bg-surface-container"
    : "rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm font-medium text-slate-100 hover:bg-slate-700";
  const hintClass = lightMode ? "text-xs text-on-surface-variant" : "text-xs text-slate-500";
  const errClass = lightMode ? "text-xs text-rose-600" : "text-xs text-rose-400";

  return (
    <div className={`space-y-2 ${className}`.trim()}>
      <div className="flex flex-wrap items-center gap-2">
        {showGeolocationButton && (
          <button type="button" className={btnClass} onClick={useMyLocation}>
            {t("map_use_my_location")}
          </button>
        )}
        <span className={hintClass}>{t("map_hint_drag_or_click")}</span>
      </div>
      {geoMsg && <p className={errClass}>{geoMsg}</p>}
      <div
        className={`relative isolate overflow-hidden rounded-xl border ${lightMode ? "border-outline-variant/40" : "border-slate-700"} min-h-[200px]`}
        style={{ height }}
      >
        <MapContainer
          center={[latitude, longitude]}
          zoom={13}
          style={{ height: "100%", width: "100%", minHeight: "200px" }}
          className={`z-[1] min-h-[inherit] ${lightMode ? "bg-surface-container-low" : "bg-slate-900"}`}
          scrollWheelZoom
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <MapLayoutFix />
          <MapEvents onMapClick={onMapClick} />
          <SyncView latitude={latitude} longitude={longitude} />
          <Marker
            position={[latitude, longitude]}
            draggable
            eventHandlers={{
              dragend: (e) => {
                const p = (e.target as L.Marker).getLatLng();
                setGeoMsg(null);
                onChange({ lat: p.lat, lng: p.lng });
              },
            }}
          />
        </MapContainer>
      </div>
      <p className={hintClass}>
        {t("map_coords_label")}: {latitude.toFixed(5)}, {longitude.toFixed(5)}
      </p>
    </div>
  );
}
