const form = document.getElementById("search-form");
const cityInput = document.getElementById("city-input");
const message = document.getElementById("message");
const result = document.getElementById("result");

const UNIT_SYMBOLS = { metric: "°C", imperial: "°F", standard: "K" };

function showMessage(text) {
  message.textContent = text;
  message.hidden = false;
}

function showError(text) {
  showMessage(text);
  result.hidden = true;
}

function unitSymbol(units) {
  return UNIT_SYMBOLS[units] || "";
}

function readDetail(body, status) {
  if (typeof body.detail === "string") {
    return body.detail;
  }
  if (Array.isArray(body.detail)) {
    return body.detail.map((item) => item.msg).join(", ");
  }
  return `Lookup failed (${status})`;
}

function describeCondition(data) {
  if (!data.conditions || data.conditions.length === 0) {
    return "unknown";
  }
  return data.conditions[0].description;
}

function renderWeather(data) {
  const symbol = unitSymbol(data.units);

  document.getElementById("result-city").textContent = data.city;
  document.getElementById("result-temp").textContent = `${data.temperature.temp} ${symbol}`;
  document.getElementById("result-feels-like").textContent = `${data.temperature.feels_like} ${symbol}`;
  document.getElementById("result-condition").textContent = describeCondition(data);
  document.getElementById("result-humidity").textContent = `${data.humidity}%`;

  message.hidden = true;
  result.hidden = false;
}

async function loadWeather(city) {
  showMessage("Loading...");

  try {
    const response = await fetch(`/weather?city=${encodeURIComponent(city)}`);
    const body = await response.json();

    if (!response.ok) {
      showError(readDetail(body, response.status));
      return;
    }

    renderWeather(body);
  } catch (error) {
    showError("Could not reach the weather server. Is it running?");
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();

  const city = cityInput.value.trim();
  if (city) {
    loadWeather(city);
  }
});