const standings = document.querySelector("#standings");
const cars = document.querySelector("#cars");
const selector = document.querySelector("#driver");
const telemetry = document.querySelector("#telemetry");
const status = document.querySelector("#status");
const colors = ["#67e8f9", "#fbbf24", "#c4b5fd", "#fb7185"];
let latest = [];
let lastSuccess = 0;

function showTelemetry() {
  localStorage.setItem("selectedDriver", selector.value);
  const driver = latest.find(item => item.driver_id === selector.value);
  telemetry.replaceChildren();
  if (!driver) return;
  const readings = {"Speed": `${driver.speed_kph.toFixed(0)} km/h`,
    "Throttle": `${(driver.throttle * 100).toFixed(0)}%`,
    "Brake": driver.brake ? "On" : "Off", "Gear": driver.gear};
  for (const [label, value] of Object.entries(readings)) {
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = label;
    description.textContent = value;
    telemetry.append(term, description);
  }
}
selector.addEventListener("change", showTelemetry);

function render(snapshot) {
  latest = snapshot.drivers;
  if (selector.options.length === 0 && latest.length > 0) {
    for (const driver of latest) selector.add(new Option(driver.driver_id, driver.driver_id));
    const saved = localStorage.getItem("selectedDriver");
    if (latest.some(driver => driver.driver_id === saved)) selector.value = saved;
  }
  standings.replaceChildren();
  cars.replaceChildren();
  for (const driver of latest) {
    const row = document.createElement("tr");
    for (const value of [driver.position, driver.driver_id, driver.progress.toFixed(2)]) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    standings.append(row);
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", driver.x);
    circle.setAttribute("cy", driver.y);
    circle.setAttribute("r", driver.driver_id === selector.value ? "0.065" : "0.045");
    circle.setAttribute("fill", colors[Number(driver.driver_id.slice(-2)) - 1] || "white");
    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = driver.driver_id;
    circle.append(title);
    cars.append(circle);
  }
  showTelemetry();
  const newest = Math.max(...latest.map(driver => driver.timestamp), 0);
  status.textContent = Date.now() / 1000 - newest > 2 ? "Telemetry stale" : "Simulation running · 5 updates/sec";
}

async function poll() {
  try {
    const response = await fetch("/api/state", {signal: AbortSignal.timeout(2000)});
    if (!response.ok) throw new Error("State request failed");
    render(await response.json());
    lastSuccess = Date.now();
  } catch (error) {
    status.textContent = `Disconnected · last update ${lastSuccess ? Math.floor((Date.now() - lastSuccess) / 1000) + "s ago" : "unavailable"}`;
  } finally {
    setTimeout(poll, 200); // Wait after completion: requests never overlap.
  }
}
poll();
