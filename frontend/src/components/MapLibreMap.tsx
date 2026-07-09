"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

export default function MapLibreMap() {
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    mapRef.current = new maplibregl.Map({
      container: mapContainer.current,
      style: "https://demotiles.maplibre.org/style.json",
      center: [-122.3035, 47.6553], // UW Seattle area
      zoom: 13,
    });

    mapRef.current.addControl(new maplibregl.NavigationControl(), "top-right");

    new maplibregl.Marker()
      .setLngLat([-122.3035, 47.6553])
      .setPopup(
        new maplibregl.Popup().setHTML(
          "<strong>UW Alert Map</strong><br />Frontend container test marker"
        )
      )
      .addTo(mapRef.current);

    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  return <div ref={mapContainer} className="map-container" />;
}