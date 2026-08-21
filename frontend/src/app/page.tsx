import MapLibreMap from "../components/MapLibreMap";

//Max hours is 720 for testing
export default function HomePage() {
  return <MapLibreMap recentHours={6} />;
}