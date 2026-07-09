import MapLibreMap from "../components/MapLibreMap";

export default function Home() {
  return (
    <main className="page">
      <header className="header">
        <h1>UW Alerts Live Map</h1>
        <p>MapLibre frontend container proof of concept</p>
      </header>

      <section className="map-shell">
        <MapLibreMap />
      </section>
    </main>
  );
}