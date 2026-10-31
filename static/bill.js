/**
 * ShelfSync - New Bill Client-side Interactivity
 * Provides real-time calculation and UX enhancements.
 * (Note: The server is the single authoritative source of truth for pricing & stock).
 */

document.addEventListener('DOMContentLoaded', function () {
  const walkinCheckbox = document.getElementById('walkin_customer');
  const customerSelect = document.getElementById('customer_id');
  const itemsContainer = document.getElementById('itemsContainer');
  const addItemBtn = document.getElementById('addItemBtn');
  const rowTemplate = document.getElementById('rowTemplate');
  const itemsCountDisplay = document.getElementById('itemsCountDisplay');
  const grandTotalDisplay = document.getElementById('grandTotalDisplay');
  const mobileGrandTotalDisplay = document.getElementById('mobileGrandTotalDisplay');

  // 1. Toggle Customer Dropdown based on Walk-in status
  if (walkinCheckbox && customerSelect) {
    walkinCheckbox.addEventListener('change', function () {
      if (this.checked) {
        customerSelect.disabled = true;
        customerSelect.value = '';
      } else {
        customerSelect.disabled = false;
        customerSelect.focus();
      }
    });
  }

  // 2. Format paise to Indian Currency String (₹1,51,060.00)
  function formatINR(paise) {
    if (isNaN(paise) || paise < 0) paise = 0;
    const rupees = Math.floor(paise / 100);
    const subPaise = paise % 100;

    let rupeesStr = rupees.toString();
    let formattedRupees = '';

    if (rupeesStr.length <= 3) {
      formattedRupees = rupeesStr;
    } else {
      const last3 = rupeesStr.substring(rupeesStr.length - 3);
      let remaining = rupeesStr.substring(0, rupeesStr.length - 3);
      const chunks = [];
      while (remaining.length > 2) {
        chunks.unshift(remaining.substring(remaining.length - 2));
        remaining = remaining.substring(0, remaining.length - 2);
      }
      if (remaining.length > 0) {
        chunks.unshift(remaining);
      }
      formattedRupees = chunks.join(',') + ',' + last3;
    }

    const padSubPaise = subPaise < 10 ? '0' + subPaise : subPaise.toString();
    return `₹${formattedRupees}.${padSubPaise}`;
  }

  // 3. Update single row calculations
  function updateRow(row) {
    const select = row.querySelector('.product-select');
    const qtyInput = row.querySelector('.item-qty');
    const priceDisplay = row.querySelector('.unit-price-display');
    const stockDisplay = row.querySelector('.stock-avail-display');
    const lineTotalDisplay = row.querySelector('.line-total-display');

    if (!select || !qtyInput) return;

    const selectedOption = select.options[select.selectedIndex];
    if (selectedOption && selectedOption.value) {
      const pricePaise = parseInt(selectedOption.getAttribute('data-price-paise'), 10) || 0;
      const stock = parseInt(selectedOption.getAttribute('data-stock'), 10) || 0;
      let qty = parseInt(qtyInput.value, 10);

      if (isNaN(qty) || qty < 1) {
        qty = 1;
      }

      priceDisplay.textContent = formatINR(pricePaise);
      stockDisplay.textContent = `${stock} available`;
      lineTotalDisplay.textContent = formatINR(pricePaise * qty);
    } else {
      priceDisplay.textContent = '₹0.00';
      stockDisplay.textContent = '0 available';
      lineTotalDisplay.textContent = '₹0.00';
    }

    updateGrandTotals();
  }

  // 4. Update overall invoice totals
  function updateGrandTotals() {
    let grandTotalPaise = 0;
    let validItemsCount = 0;

    const rows = itemsContainer.querySelectorAll('.bill-item-row');
    rows.forEach(function (row) {
      const select = row.querySelector('.product-select');
      const qtyInput = row.querySelector('.item-qty');
      const selectedOption = select ? select.options[select.selectedIndex] : null;

      if (selectedOption && selectedOption.value) {
        const pricePaise = parseInt(selectedOption.getAttribute('data-price-paise'), 10) || 0;
        let qty = parseInt(qtyInput.value, 10);
        if (isNaN(qty) || qty < 1) qty = 1;

        grandTotalPaise += pricePaise * qty;
        validItemsCount += 1;
      }
    });

    const formatted = formatINR(grandTotalPaise);
    if (grandTotalDisplay) grandTotalDisplay.textContent = formatted;
    if (mobileGrandTotalDisplay) mobileGrandTotalDisplay.textContent = formatted;
    if (itemsCountDisplay) itemsCountDisplay.textContent = validItemsCount.toString();
  }

  // 5. Attach event listeners to a row
  function attachRowEvents(row) {
    const select = row.querySelector('.product-select');
    const qtyInput = row.querySelector('.item-qty');
    const removeBtn = row.querySelector('.remove-item-btn');

    if (select) {
      select.addEventListener('change', function () {
        updateRow(row);
      });
    }

    if (qtyInput) {
      qtyInput.addEventListener('input', function () {
        updateRow(row);
      });
    }

    if (removeBtn) {
      removeBtn.addEventListener('click', function () {
        const allRows = itemsContainer.querySelectorAll('.bill-item-row');
        if (allRows.length > 1) {
          row.remove();
        } else {
          // If only 1 row remains, reset it
          if (select) select.value = '';
          if (qtyInput) qtyInput.value = 1;
          updateRow(row);
        }
        updateGrandTotals();
      });
    }
  }

  // 6. Add new item row
  if (addItemBtn && rowTemplate) {
    addItemBtn.addEventListener('click', function () {
      const clone = rowTemplate.content.cloneNode(true);
      const newRow = clone.querySelector('.bill-item-row');
      itemsContainer.appendChild(newRow);
      attachRowEvents(newRow);
      updateRow(newRow);
    });
  }

  // Initialize existing rows
  const initialRows = itemsContainer.querySelectorAll('.bill-item-row');
  initialRows.forEach(function (row) {
    attachRowEvents(row);
    updateRow(row);
  });
});
