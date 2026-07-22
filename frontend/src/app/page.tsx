import MapLibreMap from "../components/MapLibreMap";

//Max hours is 999 for testing
export default function HomePage() {
  return <MapLibreMap recentHours={6} />;
}
