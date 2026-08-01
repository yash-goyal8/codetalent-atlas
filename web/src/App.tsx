import { lazy } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/AppLayout";

/* Route-level code splitting: each page is its own lazy chunk. */
const Overview = lazy(() => import("./routes/Overview"));
const Explorer = lazy(() => import("./routes/Explorer"));
const Compare = lazy(() => import("./routes/Compare"));
const LocationDetail = lazy(() => import("./routes/LocationDetail"));
const Methodology = lazy(() => import("./routes/Methodology"));
const Recommendations = lazy(() => import("./routes/Recommendations"));
const About = lazy(() => import("./routes/About"));
const NotFound = lazy(() => import("./routes/NotFound"));

/** Route table, router-agnostic so tests can mount it in a MemoryRouter. */
export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Overview />} />
        <Route path="explore" element={<Explorer />} />
        <Route path="compare" element={<Compare />} />
        <Route path="location/:geoId" element={<LocationDetail />} />
        <Route path="methodology" element={<Methodology />} />
        <Route path="recommendations" element={<Recommendations />} />
        <Route path="about" element={<About />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
