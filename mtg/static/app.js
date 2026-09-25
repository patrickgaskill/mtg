// MTG card data reports: a single-page app over manifest.json and one JSON file
// per report. Routes live in the URL fragment so GitHub Pages can serve every
// view from index.html: "#/" is the report list, "#/<report>" shows one report,
// and hidden type-filter toggles are kept as "?field:keyword=0" after the name.

'use strict';

// Card Link Cell Renderer
class CardLinkRenderer {
  constructor() {
    this.tippyInstances = [];
  }

  init(params) {
    this.eGui = document.createElement('span');

    const cardData = params.data;
    const colDef = params.colDef;
    const value = params.value;

    if (!value) {
      this.eGui.textContent = '';
      return;
    }

    // Handle single or multiple cards
    // The supercycle aggregator provides an array of card objects via cardLinkData.
    // Other aggregators provide a single card name string (treated as-is, not split).
    let cardNames;
    const linkDataField = colDef.cardLinkData;
    if (linkDataField && cardData[linkDataField] && Array.isArray(cardData[linkDataField])) {
      // Extract card names from the structured data (supercycles)
      cardNames = cardData[linkDataField].map(cardObj => cardObj.name);
    } else {
      // Single card name - treat as complete name even if it contains commas
      cardNames = [value];
    }

    cardNames.forEach((cardName, index) => {
      if (index > 0) {
        this.eGui.appendChild(document.createTextNode(', '));
      }

      const link = document.createElement('a');
      link.className = 'card-link';
      link.textContent = cardName;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';

      // Determine the card's Scryfall URI and image
      const cardInfo = this.getCardInfo(cardData, cardName, colDef);

      if (cardInfo.scryfallUri) {
        link.href = cardInfo.scryfallUri;
      } else {
        // Fallback: search by exact card name
        link.href = `https://scryfall.com/search?q=${encodeURIComponent(`!"${cardName}"`)}`;
      }

      // Add tooltip with card image if available
      if (cardInfo.imageUri) {
        // Create image element using DOM to prevent XSS
        const img = document.createElement('img');
        img.src = cardInfo.imageUri;
        // Using DOM property assignment (not innerHTML) prevents XSS
        img.alt = `Magic: The Gathering card - ${cardName}`;
        img.className = 'card-tooltip-image';
        img.onerror = function () {
          // Replace broken image with accessible text fallback
          const fallback = document.createElement('span');
          fallback.setAttribute('role', 'img');
          fallback.setAttribute('aria-label', `Card image for ${cardName} unavailable`);
          fallback.textContent = 'Card image unavailable';

          if (this.parentNode) {
            this.parentNode.replaceChild(fallback, this);
          } else {
            console.error('Failed to replace broken card image: no parent node', {
              cardName: cardName,
              imageUri: cardInfo.imageUri
            });
          }
        };

        // Create Tippy instance for this card link.
        // Performance note: Each link gets its own instance, which has memory overhead.
        // This is acceptable because: (1) AG Grid paginates rows, limiting visible instances,
        // (2) destroy() cleans up instances when cells are removed, and (3) the user
        // experience benefit of instant tooltips outweighs using a shared singleton approach.
        const tippyInstance = tippy(link, {
          content: img,
          theme: 'card',
          placement: 'right',
          arrow: false,
          maxWidth: 'none',
          delay: [200, 0],
          trigger: 'mouseenter focus',
          // On touch devices there is no hover: emulated mouseenter on tap
          // would pop the tooltip while also following the link. Disable
          // touch-triggered tooltips so a tap just opens Scryfall.
          touch: false
        });
        this.tippyInstances.push(tippyInstance);
      }

      this.eGui.appendChild(link);
    });
  }

  getCardInfo(cardData, cardName, colDef) {
    // If column has cardLinkData specified, use that field's data
    const linkDataField = colDef.cardLinkData;

    if (linkDataField && cardData[linkDataField]) {
      // Handle array of card objects (e.g., supercycle members)
      if (Array.isArray(cardData[linkDataField])) {
        const cardInfo = cardData[linkDataField].find(c => c.name === cardName);
        if (cardInfo) {
          return {
            scryfallUri: cardInfo.scryfall_uri || null,
            imageUri: cardInfo.image_uri || null
          };
        } else {
          // Log a warning when the expected card is not found in the array
          console.warn(
            '[CardLinkRenderer] Expected card "%s" in array field "%s", but no matching entry was found. Falling back to row-level card data.',
            cardName,
            linkDataField
          );
        }
      } else {
        // Single card object
        const cardInfo = cardData[linkDataField];
        return {
          scryfallUri: cardInfo.scryfall_uri || null,
          imageUri: cardInfo.image_uri || null
        };
      }
    }

    // Fallback: look in row data itself
    return {
      scryfallUri: cardData.scryfall_uri || null,
      imageUri: cardData.image_uri || null
    };
  }

  getGui() {
    return this.eGui;
  }

  refresh(params) {
    // Return false to prevent AG Grid from refreshing this cell renderer in place.
    // Card links are static content that doesn't change based on data updates,
    // so recreating the renderer is more appropriate than refreshing.
    return false;
  }

  destroy() {
    // Clean up Tippy instances to prevent memory leaks
    if (this.tippyInstances) {
      this.tippyInstances.forEach(instance => instance.destroy());
      this.tippyInstances = [];
    }
  }
}

// Suppress AG Grid's cell focus ring on touch devices: tapping a cell draws a
// ring that serves no purpose there. Matches the touch media query in the CSS.
const isTouchDevice = window.matchMedia('(hover: none) and (pointer: coarse)').matches;

const state = {
  manifest: null,
  reportsByName: new Map(),
  dataCache: new Map(),
  gridApi: null,
  currentReport: null,
  typeFilterState: {},
};

const el = (id) => document.getElementById(id);

function parseRoute() {
  const hash = window.location.hash.replace(/^#\/?/, '');
  const [name, query = ''] = hash.split('?');
  return { name: decodeURIComponent(name), params: new URLSearchParams(query) };
}

function showError(message) {
  const error = el('app-error');
  error.textContent = message;
  error.hidden = !message;
}

function fetchJson(url) {
  return fetch(url).then((response) => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  });
}

function loadReportData(report) {
  if (!state.dataCache.has(report.name)) {
    const request = fetchJson(report.dataFile).catch((error) => {
      state.dataCache.delete(report.name);
      throw error;
    });
    state.dataCache.set(report.name, request);
  }
  return state.dataCache.get(report.name);
}

function renderNavigation(manifest) {
  const select = el('nav-select');
  const list = el('report-list');

  for (const report of manifest.reports) {
    const option = document.createElement('option');
    option.value = report.name;
    option.textContent = report.displayName;
    select.appendChild(option);

    const item = document.createElement('li');
    item.className = 'report-item';
    const link = document.createElement('a');
    link.href = `#/${encodeURIComponent(report.name)}`;
    link.textContent = report.displayName;
    const description = document.createElement('p');
    description.className = 'report-description';
    description.textContent = report.description;
    const rows = document.createElement('span');
    rows.className = 'report-rows';
    rows.textContent = ` (${report.rowCount.toLocaleString()} rows)`;
    description.appendChild(rows);
    item.append(link, description);
    list.appendChild(item);
  }

  select.addEventListener('change', () => {
    window.location.hash = select.value ? `#/${encodeURIComponent(select.value)}` : '#/';
  });

  el('generated-at').textContent = `Data from Scryfall as of ${manifest.generatedAt}.`;
}

function destroyGrid() {
  if (state.gridApi) {
    state.gridApi.destroy();
    state.gridApi = null;
  }
  state.currentReport = null;
}

function showHome() {
  destroyGrid();
  document.body.classList.add('is-home');
  document.title = 'MTG Card Data Reports';
  el('nav-select').value = '';
  el('report-view').hidden = true;
  el('home-view').hidden = false;
}

function filterKey(filter) {
  return `${filter.field}:${filter.keyword}`;
}

function updateFilterUrl(report) {
  const params = new URLSearchParams();
  for (const [key, shown] of Object.entries(state.typeFilterState)) {
    if (!shown) params.set(key, '0');
  }
  const query = params.toString();
  const hash = `#/${encodeURIComponent(report.name)}${query ? `?${query}` : ''}`;
  history.replaceState(null, '', hash);
}

function renderTypeFilters(report, params) {
  const container = el('report-filters');
  container.replaceChildren();
  state.typeFilterState = {};

  for (const filter of report.typeFilters) {
    const key = filterKey(filter);
    const shown = params.get(key) !== '0';
    state.typeFilterState[key] = shown;

    const label = document.createElement('label');
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = shown;
    checkbox.addEventListener('change', () => {
      state.typeFilterState[key] = checkbox.checked;
      state.gridApi?.onFilterChanged();
      updateFilterUrl(report);
    });
    label.append(checkbox, ` Show ${filter.label}`);
    container.appendChild(label);
  }
  container.hidden = report.typeFilters.length === 0;
}

function isExternalFilterPresent() {
  return Object.values(state.typeFilterState).some((shown) => !shown);
}

function doesExternalFilterPass(node) {
  for (const [key, shown] of Object.entries(state.typeFilterState)) {
    if (shown) continue;
    const separator = key.indexOf(':');
    const field = key.slice(0, separator);
    const keyword = key.slice(separator + 1);
    const value = node.data[field] || '';
    // Match whole word: "Plane" shouldn't match "Planeswalker"
    const regex = new RegExp(`\\b${keyword}\\b`);
    if (regex.test(value)) return false;
  }
  return true;
}

function showReport(report, params) {
  document.body.classList.remove('is-home');
  el('home-view').hidden = true;
  el('report-view').hidden = false;
  el('nav-select').value = report.name;

  if (state.currentReport === report.name) {
    // Only the filter query changed (e.g. back/forward); sync the toggles.
    renderTypeFilters(report, params);
    state.gridApi?.onFilterChanged();
    return;
  }

  destroyGrid();
  state.currentReport = report.name;
  document.title = report.displayName;
  el('report-title').textContent = report.displayName;

  // Explanations are trusted HTML rendered from this repository's Markdown.
  const explanation = el('report-explanation');
  explanation.innerHTML = report.explanationHtml;
  explanation.hidden = !report.explanationHtml;

  renderTypeFilters(report, params);

  const gridOptions = {
    theme: 'legacy',
    columnDefs: report.columnDefs,
    rowData: null,
    loading: true,
    suppressCellFocus: isTouchDevice,
    defaultColDef: {
      sortable: true,
      filter: true,
      resizable: true,
      minWidth: 80,
    },
    components: {
      cardLinkRenderer: CardLinkRenderer,
    },
    pagination: true,
    paginationPageSize: 100,
    isExternalFilterPresent,
    doesExternalFilterPass,
    onFirstDataRendered: (event) => {
      // Auto-size all columns to fit content on initial load
      event.api.autoSizeAllColumns(false);
    },
  };

  const gridApi = agGrid.createGrid(el('myGrid'), gridOptions);
  state.gridApi = gridApi;

  loadReportData(report)
    .then((data) => {
      if (state.gridApi !== gridApi) return; // navigated away meanwhile
      gridApi.setGridOption('rowData', data);
      gridApi.setGridOption('loading', false);
    })
    .catch((error) => {
      console.error('Error loading data:', error);
      if (state.gridApi !== gridApi) return;
      gridApi.setGridOption('loading', false);

      // Create error element using DOM API to prevent XSS
      const errorSpan = document.createElement('span');
      errorSpan.className = 'error-message';
      errorSpan.textContent = `Error loading data: ${error.message}`;

      gridApi.setGridOption('overlayNoRowsTemplate', errorSpan.outerHTML);
      gridApi.showNoRowsOverlay();
    });
}

function route() {
  showError('');
  const { name, params } = parseRoute();
  if (!name) {
    showHome();
    return;
  }
  const report = state.reportsByName.get(name);
  if (!report) {
    showHome();
    showError(`Unknown report "${name}".`);
    return;
  }
  showReport(report, params);
}

fetchJson('manifest.json')
  .then((manifest) => {
    state.manifest = manifest;
    for (const report of manifest.reports) {
      state.reportsByName.set(report.name, report);
    }
    renderNavigation(manifest);
    window.addEventListener('hashchange', route);
    route();
  })
  .catch((error) => {
    console.error('Error loading manifest:', error);
    showError(`Error loading reports: ${error.message}`);
  });
