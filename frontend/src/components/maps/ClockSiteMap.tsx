import L from "leaflet";
import { useEffect } from "react";
import { Circle, MapContainer, Marker, TileLayer, useMap } from "react-leaflet";
import { useTranslation } from "react-i18next";
import { ensureLeafletDefaultIcon } from "../../lib/leafletDefaultIcon";
import "leaflet/dist/leaflet.css";

ensureLeafletDefaultIcon();

const jobMarkerIcon = L.divIcon({
  className: "clock-site-map-marker clock-site-map-marker--job",
  html: `<span class="clock-site-map-dot clock-site-map-dot--job" title=""></span>`,
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

const youMarkerIcon = L.divIcon({
  className: "clock-site-map-marker clock-site-map-marker--you",
  html: `<span class="clock-site-map-dot clock-site-map-dot--you" title=""></span>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

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

function FitJobAndYou({
  jobLat,
  jobLng,
  radiusM,
  youLat,
  youLng,
}: {
  jobLat: number;
  jobLng: number;
  radiusM: number;
  youLat: number | null;
  youLng: number | null;
}) {
  const map = useMap();
  useEffect(() => {
    let canceled = false;
    // Leaflet needs the circle to be attached to a map before calling `getBounds()`.
    // Without `addTo(map)`, Leaflet's internal projection lookup fails with `_map is undefined`.
    const circle = L.circle([jobLat, jobLng], { radius: radiusM }).addTo(map);
    const bounds = circle.getBounds();
    if (youLat != null && youLng != null) {
      bounds.extend([youLat, youLng]);
    }
    const fit = () => {
      if (canceled) return;
      map.invalidateSize({ animate: false });
      map.fitBounds(bounds, { padding: [28, 28], maxZoom: 17 });
    };
    const id = requestAnimationFrame(() => {
      requestAnimationFrame(fit);
    });
    return () => {
      canceled = true;
      cancelAnimationFrame(id);
      circle.remove();
    };
  }, [map, jobLat, jobLng, radiusM, youLat, youLng]);
  return null;
}

type Props = {
  jobSiteLat: number;
  jobSiteLng: number;
  geofenceRadiusM: number;
  youLat: number | null;
  youLng: number | null;
  height?: string;
  className?: string;
};

export function ClockSiteMap({
  jobSiteLat,
  jobSiteLng,
  geofenceRadiusM,
  youLat,
  youLng,
  height = "240px",
  className = "",
}: Props) {
  const { t } = useTranslation();

  return (
    <div className={`space-y-2 ${className}`.trim()}>
      <p className="text-xs text-on-surface-variant">{t("clock_map_caption")}</p>
      <ul className="flex flex-wrap gap-4 text-xs text-on-surface-variant">
        <li className="flex items-center gap-2">
          <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full bg-[#2563eb] ring-2 ring-white shadow" aria-hidden />
          <span>{t("clock_map_job_site")}</span>
        </li>
        <li className="flex items-center gap-2">
          <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full bg-[#16a34a] ring-2 ring-white shadow" aria-hidden />
          <span>{t("clock_map_your_location")}</span>
        </li>
      </ul>
      <div
        className="relative isolate overflow-hidden rounded-xl border border-outline-variant/40 min-h-[200px]"
        style={{ height }}
      >
        <MapContainer
          center={[jobSiteLat, jobSiteLng]}
          zoom={15}
          style={{ height: "100%", width: "100%", minHeight: "200px" }}
          className="z-[1] min-h-[inherit] bg-surface-container-low"
          scrollWheelZoom
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <MapLayoutFix />
          <FitJobAndYou
            jobLat={jobSiteLat}
            jobLng={jobSiteLng}
            radiusM={geofenceRadiusM}
            youLat={youLat}
            youLng={youLng}
          />
          <Circle
            center={[jobSiteLat, jobSiteLng]}
            radius={geofenceRadiusM}
            pathOptions={{
              color: "#2563eb",
              fillColor: "#2563eb",
              fillOpacity: 0.12,
              weight: 2,
            }}
          />
          <Marker position={[jobSiteLat, jobSiteLng]} icon={jobMarkerIcon} title={t("clock_map_job_site")} />
          {youLat != null && youLng != null && (
            <Marker position={[youLat, youLng]} icon={youMarkerIcon} title={t("clock_map_your_location")} />
          )}
        </MapContainer>
      </div>
      <style>{`
        .clock-site-map-marker {
          background: transparent !important;
          border: none !important;
        }
        .clock-site-map-dot {
          display: block;
          width: 100%;
          height: 100%;
          border-radius: 9999px;
          box-shadow: 0 1px 4px rgba(0,0,0,0.35);
          border: 2px solid #fff;
        }
        .clock-site-map-dot--job { background: #2563eb; }
        .clock-site-map-dot--you { background: #16a34a; }
      `}</style>
    </div>
  );
}
