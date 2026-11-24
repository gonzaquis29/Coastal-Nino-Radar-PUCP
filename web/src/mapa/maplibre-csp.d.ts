// La variante CSP de MapLibre trae el worker en un archivo aparte (la política de la app no admite blob:).
/// <reference types="vite/client" />
/// <reference types="geojson" />
declare module "maplibre-gl/dist/maplibre-gl-csp" {
  import maplibregl from "maplibre-gl";
  export default maplibregl;
}
