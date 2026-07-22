import MapLibreMap from "../components/MapLibreMap";

//Max hours is 168 for testing
export default function HomePage() {
  return <MapLibreMap recentHours={6} />;
}