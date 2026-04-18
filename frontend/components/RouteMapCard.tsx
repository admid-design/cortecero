import React, { useEffect, useMemo, useRef, useState } from "react";
import type { DriverPositionOut, RouteStopStatus, RoutingRoute } from "../lib/api";

type LocalDriverPosition = {
  lat?: number | null;
  lng?: number | null;
  heading?: number | null;
  updated_at?: string | null;
};

type RouteMapPoint = {
  stopId: string;
  sequenceNumber: number;
  status: RouteStopStatus;
  lat: number;
  lng: number;
};

type GoogleMapsWindow = Window & {
  google?: {
    maps?: any;
  };
  __corteCeroGoogleMapsPromise?: Promise<void>;
};

// Depósito: POLIGON INDUSTRIAL SON LLAUT, Santa Maria del Camí, Mallorca
const FALLBACK_DEPOT_LAT = 39.648;
const FALLBACK_DEPOT_LNG = 2.787;

function parseCoordinate(value: number | null | undefined): number | null {
  if (typeof value !== "number") return null;
  if (!Number.isFinite(value)) return null;
  return value;
}

/** Genera una URL de icono SVG con emoji para usar como marcador de Google Maps */
function emojiIconUrl(emoji: string, size = 36): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}"><text y="${Math.round(size * 0.85)}" font-size="${Math.round(size * 0.8)}" x="${Math.round(size / 2)}" text-anchor="middle">${emoji}</text></svg>`;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

function stopStatusColor(status: RouteStopStatus): string {
  if (status === "completed") return "#16a34a";
  if (status === "arrived" || status === "en_route") return "#2563eb";
  if (status === "failed") return "#dc2626";
  if (status === "skipped") return "#6b7280";
  return "#f59e0b";
}

function decodeGoogleEncodedPolyline(encoded: string): Array<{ lat: number; lng: number }> {
  const points: Array<{ lat: number; lng: number }> = [];
  let index = 0;
  let lat = 0;
  let lng = 0;

  while (index < encoded.length) {
    let result = 0;
    let shift = 0;
    let byte = 0;
    do {
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    const deltaLat = (result & 1) !== 0 ? ~(result >> 1) : result >> 1;
    lat += deltaLat;

    result = 0;
    shift = 0;
    do {
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    const deltaLng = (result & 1) !== 0 ? ~(result >> 1) : result >> 1;
    lng += deltaLng;

    points.push({ lat: lat / 1e5, lng: lng / 1e5 });
  }

  return points;
}

async function loadGoogleMapsScript(apiKey: string): Promise<void> {
  if (typeof window === "undefined") return;
  if (!apiKey) throw new Error("MISSING_MAPS_API_KEY");

  const mapsWindow = window as GoogleMapsWindow;
  if (mapsWindow.google?.maps) return;
  if (mapsWindow.__corteCeroGoogleMapsPromise) {
    await mapsWindow.__corteCeroGoogleMapsPromise;
    return;
  }

  mapsWindow.__corteCeroGoogleMapsPromise = new Promise<void>((resolve, reject) => {
    const existingScript = document.querySelector<HTMLScriptElement>('script[data-cortecero-google-maps="1"]');
    if (existingScript) {
      existingScript.addEventListener("load", () => resolve(), { once: true });
      existingScript.addEventListener("error", () => reject(new Error("GOOGLE_MAPS_LOAD_ERROR")), { once: true });
      return;
    }

    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}`;
    script.async = true;
    script.defer = true;
    script.dataset.corteceroGoogleMaps = "1";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("GOOGLE_MAPS_LOAD_ERROR"));
    document.head.appendChild(script);
  });

  await mapsWindow.__corteCeroGoogleMapsPromise;
}

type RouteMapCardProps = {
  route: RoutingRoute | null;
  /** Posición actual del conductor — actualizada por polling desde el padre. */
  driverPosition?: LocalDriverPosition | null;
  /** Vehículo seleccionado en el panel de flota (sin ruta activa). */
  selectedVehicleId?: string | null;
  selectedVehicleName?: string | null;
  /** Posiciones de toda la flota activa — cuando se provee, reemplaza el marcador único de conductor. */
  activePositions?: DriverPositionOut[] | null;
};

export function RouteMapCard({ route, driverPosition, selectedVehicleId, selectedVehicleName, activePositions }: RouteMapCardProps) {
  const mapRef = useRef<HTMLDivElement | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);
  const [mapsLoaded, setMapsLoaded] = useState(false);

  const mapApiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? "";
  // Usar coordenadas de env var o fallback a Santa Maria del Camí
  const depotLat = parseCoordinate(process.env.NEXT_PUBLIC_DEPOT_LAT ? Number(process.env.NEXT_PUBLIC_DEPOT_LAT) : null) ?? FALLBACK_DEPOT_LAT;
  const depotLng = parseCoordinate(process.env.NEXT_PUBLIC_DEPOT_LNG ? Number(process.env.NEXT_PUBLIC_DEPOT_LNG) : null) ?? FALLBACK_DEPOT_LNG;

  const stopPoints = useMemo<RouteMapPoint[]>(
    () =>
      (route?.stops ?? [])
        .map((stop) => {
          const lat = parseCoordinate(stop.customer_lat);
          const lng = parseCoordinate(stop.customer_lng);
          if (lat == null || lng == null) return null;
          return {
            stopId: stop.id,
            sequenceNumber: stop.sequence_number,
            status: stop.status,
            lat,
            lng,
          } satisfies RouteMapPoint;
        })
        .filter((point): point is RouteMapPoint => point != null)
        .sort((a, b) => a.sequenceNumber - b.sequenceNumber),
    [route?.stops],
  );

  const transitionGeometryPaths = useMemo<Array<Array<{ lat: number; lng: number }>>>(() => {
    const geometry = route?.route_geometry;
    if (!geometry || geometry.encoding !== "google_encoded_polyline") return [];
    return geometry.transition_polylines
      .map((encoded) => {
        if (!encoded || typeof encoded !== "string") return [];
        try {
          return decodeGoogleEncodedPolyline(encoded);
        } catch {
          return [];
        }
      })
      .filter((path) => path.length > 1);
  }, [route?.route_geometry]);

  const hasTransitionGeometry = transitionGeometryPaths.length > 0;

  useEffect(() => {
    let cancelled = false;

    if (!mapApiKey) {
      setMapError("Configura NEXT_PUBLIC_GOOGLE_MAPS_API_KEY para ver el mapa.");
      setMapsLoaded(false);
      return;
    }

    loadGoogleMapsScript(mapApiKey)
      .then(() => {
        if (cancelled) return;
        setMapError(null);
        setMapsLoaded(true);
      })
      .catch(() => {
        if (cancelled) return;
        setMapError("No se pudo cargar Google Maps JavaScript API.");
        setMapsLoaded(false);
      });

    return () => {
      cancelled = true;
    };
  }, [mapApiKey]);

  useEffect(() => {
    if (!mapsLoaded || !mapRef.current) return;

    const mapsWindow = window as GoogleMapsWindow;
    const maps = mapsWindow.google?.maps;
    if (!maps) return;

    const map = new maps.Map(mapRef.current, {
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: false,
      center: { lat: depotLat, lng: depotLng },
      zoom: 11,
      zoomControlOptions: {
        position: maps.ControlPosition.LEFT_CENTER,
      },
    });

    const bounds = new maps.LatLngBounds();
    const markers: Array<{ setMap: (map: any) => void }> = [];
    const polylines: Array<{ setMap: (map: any) => void }> = [];

    // Icono de depósito (almacén)
    const depotIcon = {
      url: emojiIconUrl("🏭", 36),
      scaledSize: new maps.Size(36, 36),
      anchor: new maps.Point(18, 30),
    };

    markers.push(
      new maps.Marker({
        map,
        position: { lat: depotLat, lng: depotLng },
        title: "Depósito — Son Llaut, Santa Maria del Camí",
        icon: depotIcon,
        zIndex: 10,
      }),
    );
    bounds.extend({ lat: depotLat, lng: depotLng });

    const fallbackPath: Array<{ lat: number; lng: number }> = [{ lat: depotLat, lng: depotLng }];

    for (const stop of stopPoints) {
      // Icono de caja/paquete con color de estado como fondo
      const boxIcon = {
        url: emojiIconUrl("📦", 34),
        scaledSize: new maps.Size(34, 34),
        anchor: new maps.Point(17, 28),
      };
      const marker = new maps.Marker({
        map,
        position: { lat: stop.lat, lng: stop.lng },
        title: `Parada #${stop.sequenceNumber}`,
        icon: boxIcon,
        label: {
          text: String(stop.sequenceNumber),
          color: "#ffffff",
          fontSize: "10px",
          fontWeight: "700",
          className: "map-stop-label",
        },
        zIndex: 5,
      });
      markers.push(marker);
      bounds.extend({ lat: stop.lat, lng: stop.lng });
      fallbackPath.push({ lat: stop.lat, lng: stop.lng });
    }

    if (hasTransitionGeometry) {
      for (const path of transitionGeometryPaths) {
        for (const point of path) {
          bounds.extend(point);
        }
        polylines.push(
          new maps.Polyline({
            path,
            map,
            geodesic: true,
            strokeColor: "#2563eb",
            strokeOpacity: 0.9,
            strokeWeight: 4,
          }),
        );
      }
    } else if (fallbackPath.length >= 2) {
      polylines.push(
        new maps.Polyline({
          path: fallbackPath,
          map,
          geodesic: true,
          strokeColor: "#64748b",
          strokeOpacity: 0.75,
          strokeWeight: 4,
        }),
      );
    }

    // fitBounds solo cuando hay paradas — sin paradas se mantiene zoom:11 inicial
    if (stopPoints.length > 0 && !bounds.isEmpty()) {
      map.fitBounds(bounds);
    }

    return () => {
      for (const marker of markers) marker.setMap(null);
      for (const polyline of polylines) polyline.setMap(null);
    };
  }, [mapsLoaded, stopPoints, depotLat, depotLng, hasTransitionGeometry, transitionGeometryPaths, route]);

  // Marcador de vehículo seleccionado — independiente del redibujado del mapa, sin cambio de zoom
  const selectedVehicleMarkerRef = useRef<{ setPosition: (pos: any) => void; setMap: (map: any) => void } | null>(null);

  useEffect(() => {
    if (!mapsLoaded) return;
    const mapsWindow = window as GoogleMapsWindow;
    const maps = mapsWindow.google?.maps;
    if (!maps || !mapRef.current) return;

    // Limpiar marcador anterior
    selectedVehicleMarkerRef.current?.setMap(null);
    selectedVehicleMarkerRef.current = null;

    // Solo mostrar cuando no hay ruta activa y hay vehículo seleccionado
    if (route || !selectedVehicleId) return;

    const mapObj = (mapRef.current as any).__gm_map ?? mapInstanceRef.current;
    if (!mapObj) return;

    selectedVehicleMarkerRef.current = new maps.Marker({
      map: mapObj,
      position: { lat: depotLat, lng: depotLng + 0.002 },
      title: selectedVehicleName ?? "Vehículo seleccionado",
      icon: {
        url: emojiIconUrl("🚚", 40),
        scaledSize: new maps.Size(40, 40),
        anchor: new maps.Point(20, 34),
      },
      zIndex: 20,
    });
    // Sin setCenter ni setZoom — el mapa mantiene su posición actual
  }, [mapsLoaded, selectedVehicleId, selectedVehicleName, route, depotLat, depotLng]);

  // Marcador separado para el conductor — se actualiza sin redibujar todo el mapa
  const driverMarkerRef = useRef<{ setPosition: (pos: any) => void; setMap: (map: any) => void } | null>(null);
  const mapInstanceRef = useRef<any>(null);
  // Marcadores de flota — uno por conductor activo (fleet view)
  const activeDriverMarkersRef = useRef<Array<{ setPosition: (pos: any) => void; setMap: (map: any) => void }>>([]);

  useEffect(() => {
    if (!mapsLoaded || !mapRef.current) return;
    const mapsWindow = window as GoogleMapsWindow;
    const maps = mapsWindow.google?.maps;
    if (!maps) return;
    // Guardamos referencia al mapa cuando se crea
    if (!mapInstanceRef.current) {
      // El mapa ya existe en el DOM — lo recuperamos del ref
      mapInstanceRef.current = (mapRef.current as any).__gm_map ?? null;
    }
  }, [mapsLoaded]);

  useEffect(() => {
    if (!mapsLoaded) return;
    const mapsWindow = window as GoogleMapsWindow;
    const maps = mapsWindow.google?.maps;
    if (!maps || !mapRef.current) return;

    // En fleet view (activePositions disponibles) se suprimen los marcadores de conductor único
    const fleetMode = activePositions != null && activePositions.length > 0;
    if (fleetMode) {
      driverMarkerRef.current?.setMap(null);
      driverMarkerRef.current = null;
      return;
    }

    const driverLat = parseCoordinate(driverPosition?.lat ?? null);
    const driverLng = parseCoordinate(driverPosition?.lng ?? null);

    if (driverLat == null || driverLng == null) {
      // Limpiar marcador si ya no hay posición
      driverMarkerRef.current?.setMap(null);
      driverMarkerRef.current = null;
      return;
    }

    // Recuperar instancia del mapa desde el div (Google Maps la adjunta internamente)
    const mapEl = mapRef.current;
    const mapObj = (mapEl as any).__gm_map ?? mapInstanceRef.current;
    if (!mapObj) return;

    if (driverMarkerRef.current) {
      // Actualizar posición del marcador existente
      driverMarkerRef.current.setPosition({ lat: driverLat, lng: driverLng });
    } else {
      // Crear marcador nuevo
      driverMarkerRef.current = new maps.Marker({
        map: mapObj,
        position: { lat: driverLat, lng: driverLng },
        title: "Conductor en ruta",
        icon: {
          url: emojiIconUrl("🚚", 40),
          scaledSize: new maps.Size(40, 40),
          anchor: new maps.Point(20, 34),
        },
        zIndex: 999,
      });
    }
  }, [mapsLoaded, driverPosition, activePositions]);

  // Marcadores de flota — actualizados de forma independiente cuando llegan posiciones activas
  useEffect(() => {
    if (!mapsLoaded) return;
    const mapsWindow = window as GoogleMapsWindow;
    const maps = mapsWindow.google?.maps;
    if (!maps || !mapRef.current) return;

    // Limpiar marcadores anteriores
    for (const m of activeDriverMarkersRef.current) m.setMap(null);
    activeDriverMarkersRef.current = [];

    if (!activePositions || activePositions.length === 0) return;

    const mapEl = mapRef.current;
    const mapObj = (mapEl as any).__gm_map ?? mapInstanceRef.current;
    if (!mapObj) return;

    for (const pos of activePositions) {
      const lat = parseCoordinate(pos.lat);
      const lng = parseCoordinate(pos.lng);
      if (lat == null || lng == null) continue;

      const marker = new maps.Marker({
        map: mapObj,
        position: { lat, lng },
        title: `Conductor ${pos.driver_id.slice(0, 8)}`,
        icon: {
          url: emojiIconUrl("🚚", 40),
          scaledSize: new maps.Size(40, 40),
          anchor: new maps.Point(20, 34),
        },
        zIndex: 998,
      });
      activeDriverMarkersRef.current.push(marker);
    }
  }, [mapsLoaded, activePositions]);

  return (
    <div className="card grid route-map-card">
      <h4 style={{ margin: 0 }}>Mapa de Ruta</h4>
      <div className="row route-map-meta" style={{ gap: 6 }}>
        <span className="pill">paradas geo-ready: {stopPoints.length}</span>
        {depotLat != null && depotLng != null && <span className="pill">depot: disponible</span>}
        {hasTransitionGeometry ? <span className="pill">geometría vial: disponible</span> : <span className="pill">fallback: recto</span>}
      </div>
      {route && (
        <div className="row route-map-legend" style={{ gap: 8 }}>
          <span className="route-legend-item">
            <span className="route-dot pending" /> pending
          </span>
          <span className="route-legend-item">
            <span className="route-dot moving" /> en_route/arrived
          </span>
          <span className="route-legend-item">
            <span className="route-dot completed" /> completed
          </span>
          <span className="route-legend-item">
            <span className="route-dot failed" /> failed
          </span>
          {activePositions && activePositions.length > 0 ? (
            <span className="route-legend-item">
              <span className="route-dot" style={{ background: "#7c3aed" }} /> flota activa ({activePositions.length})
            </span>
          ) : driverPosition && (
            <span className="route-legend-item">
              <span className="route-dot" style={{ background: "#7c3aed" }} /> conductor
            </span>
          )}
        </div>
      )}
      <div ref={mapRef} className="route-map-canvas" />
    </div>
  );
}
