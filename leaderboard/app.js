const CSV_PATH = "data/leaderboard.csv";
const DEFAULT_SORT_COLUMN = "score";
const DEFAULT_SORT_DIRECTION = "desc";

const statusEl = document.getElementById("leaderboard-status");
const tableHostEl = document.getElementById("leaderboard-table");
const rowCountEl = document.getElementById("row-count");
const searchInputEl = document.getElementById("leaderboard-search");

let state = {
  rows: [],
  headers: [],
  sortColumn: DEFAULT_SORT_COLUMN,
  sortDirection: DEFAULT_SORT_DIRECTION,
  searchQuery: "",
};

function parseCsvLine(line) {
  const cells = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    const nextChar = line[i + 1];

    if (char === '"') {
      if (inQuotes && nextChar === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === "," && !inQuotes) {
      cells.push(current.trim());
      current = "";
      continue;
    }

    current += char;
  }

  cells.push(current.trim());
  return cells;
}

function parseCsv(text) {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length === 0) {
    return { headers: [], rows: [] };
  }

  const headers = parseCsvLine(lines[0]);
  const rows = lines.slice(1).map((line) => {
    const values = parseCsvLine(line);
    const row = {};

    headers.forEach((header, index) => {
      row[header] = values[index] ?? "";
    });

    return row;
  });

  return { headers, rows };
}

function normalizeNumeric(value) {
  if (typeof value !== "string") {
    return "";
  }

  // Drop an uncertainty suffix
  const mainValue = value.split("±")[0];
  return mainValue.replace(/[%$,]/g, "").trim();
}

function isNumericValue(value) {
  const normalized = normalizeNumeric(value);
  return normalized !== "" && !Number.isNaN(Number(normalized));
}

function toComparableValue(value) {
  if (isNumericValue(value)) {
    return Number(normalizeNumeric(value));
  }

  return String(value).toLowerCase();
}

function sortRows(rows, column, direction) {
  const directionFactor = direction === "asc" ? 1 : -1;

  return [...rows].sort((left, right) => {
    const a = toComparableValue(left[column] ?? "");
    const b = toComparableValue(right[column] ?? "");

    if (a < b) {
      return -1 * directionFactor;
    }

    if (a > b) {
      return 1 * directionFactor;
    }

    return 0;
  });
}

function prettifyHeader(header) {
  return header.replace(/_/g, " ");
}

// Render multi-word headers across multiple lines
function renderHeaderLabel(th, header, arrow) {
  const words = prettifyHeader(header).split(" ");

  words.forEach((word, index) => {
    if (index > 0) {
      th.appendChild(document.createElement("br"));
    }
    th.appendChild(document.createTextNode(word));
  });

  if (arrow) {
    th.appendChild(document.createTextNode(arrow));
  }
}

function filterRows(rows, query) {
  const normalizedQuery = query.trim().toLowerCase();

  if (!normalizedQuery) {
    return rows;
  }

  return rows.filter((row) =>
    Object.values(row).some((value) =>
      String(value).toLowerCase().includes(normalizedQuery)
    )
  );
}

function renderTable() {
  const { headers, rows, sortColumn, sortDirection, searchQuery } = state;
  const filteredRows = filterRows(rows, searchQuery);
  const sortedRows = sortRows(filteredRows, sortColumn, sortDirection);

  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");

  headers.forEach((header) => {
    const th = document.createElement("th");
    const isActive = sortColumn === header;
    const arrow = isActive ? (sortDirection === "asc" ? " ↑" : " ↓") : "";

    renderHeaderLabel(th, header, arrow);
    th.scope = "col";
    th.classList.toggle("sort-active", isActive);
    th.addEventListener("click", () => {
      const nextDirection =
        state.sortColumn === header && state.sortDirection === "desc"
          ? "asc"
          : "desc";

      state = {
        ...state,
        sortColumn: header,
        sortDirection: nextDirection,
      };

      renderTable();
    });
    headerRow.appendChild(th);
  });

  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");

  sortedRows.forEach((row) => {
    const tr = document.createElement("tr");

    headers.forEach((header) => {
      const td = document.createElement("td");
      const value = row[header] ?? "";

      if (header === "rank") {
        const badge = document.createElement("span");
        badge.className = "rank-badge mono";
        badge.textContent = value;
        td.appendChild(badge);
      } else {
        td.textContent = value;
      }

      if (isNumericValue(value)) {
        td.classList.add("mono");
      }

      tr.appendChild(td);
    });

    tbody.appendChild(tr);
  });

  table.appendChild(tbody);
  tableHostEl.innerHTML = "";
  tableHostEl.appendChild(table);
  tableHostEl.hidden = false;
  statusEl.hidden = true;
}

function setStatus(message) {
  statusEl.textContent = message;
  statusEl.hidden = false;
}

function loadParsedData(headers, rows) {
  if (!headers.length || !rows.length) {
    throw new Error("Leaderboard CSV is empty");
  }

  state = {
    ...state,
    headers,
    rows,
    sortColumn: headers.includes(DEFAULT_SORT_COLUMN)
      ? DEFAULT_SORT_COLUMN
      : headers[0],
    sortDirection: DEFAULT_SORT_DIRECTION,
  };

  renderTable();
}

function loadCsvText(csvText) {
  const { headers, rows } = parseCsv(csvText);
  loadParsedData(headers, rows);
}

async function loadLeaderboard() {
  try {
    const response = await fetch(CSV_PATH, { cache: "no-store" });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const csvText = await response.text();
    loadCsvText(csvText);
  } catch (error) {
    setStatus(
      "Could not load leaderboard data."
    );
    console.error(error);
  }
}

searchInputEl?.addEventListener("input", (event) => {
  state = {
    ...state,
    searchQuery: event.target.value ?? "",
  };

  renderTable();
});

loadLeaderboard();
