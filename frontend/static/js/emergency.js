(() => {
  'use strict';

  // DOM Elements
  const form = document.getElementById('emergency-search-form');
  const emergencyPanel = document.getElementById('emergency-embedded-panel');
  const toggleBtn = document.getElementById('toggle-emergency-btn');
  const closePanelBtn = document.getElementById('close-emergency-panel');
  const emergencyChoiceCard = document.getElementById('emergency-choice-card');

  const locationButton = document.getElementById('use-location-button');
  const locationStatus = document.getElementById('location-status');
  const citySelect = document.getElementById('city-select');
  const submitButton = document.getElementById('find-hospitals-button');
  const resultsSection = document.getElementById('hospital-results');
  const resultsGrid = document.getElementById('hospital-results-grid');
  const resultsCount = document.getElementById('results-count');
  const resultsSubtitle = document.getElementById('results-subtitle');

  let coordinates = null;

  // Toast Notification helper
  function showToast(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', 'status');
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(8px)';
      toast.style.transition = 'all 0.25s ease';
      setTimeout(() => toast.remove(), 250);
    }, 4000);
  }

  // Toggle Emergency Panel
  function openEmergencyPanel() {
    if (!emergencyPanel) return;
    emergencyPanel.hidden = false;
    emergencyPanel.removeAttribute('hidden');
    emergencyPanel.style.display = 'block';
    if (emergencyChoiceCard) {
      emergencyChoiceCard.classList.add('active-portal');
    }
    if (toggleBtn) {
      toggleBtn.innerHTML = 'Emergency Active ↓ <span aria-hidden="true">▼</span>';
    }
    emergencyPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    showToast('Emergency SOS interface activated.', 'info');
  }

  function closeEmergencyPanel() {
    if (!emergencyPanel) return;
    emergencyPanel.hidden = true;
    emergencyPanel.setAttribute('hidden', '');
    emergencyPanel.style.display = 'none';
    if (emergencyChoiceCard) {
      emergencyChoiceCard.classList.remove('active-portal');
    }
    if (toggleBtn) {
      toggleBtn.innerHTML = 'Open Emergency SOS <span aria-hidden="true">→</span>';
    }
  }

  if (toggleBtn) {
    toggleBtn.addEventListener('click', (e) => {
      e.preventDefault();
      if (emergencyPanel.hidden || emergencyPanel.style.display === 'none') {
        openEmergencyPanel();
      } else {
        closeEmergencyPanel();
      }
    });
  }

  if (closePanelBtn) {
    closePanelBtn.addEventListener('click', (e) => {
      e.preventDefault();
      closeEmergencyPanel();
    });
  }

  // Auto-open if query param or hash requests emergency
  const urlParams = new URLSearchParams(window.location.search);
  const initialMode = document.body.dataset.initialMode || '';
  if (urlParams.get('mode') === 'emergency' || window.location.hash === '#emergency' || initialMode === 'emergency') {
    setTimeout(openEmergencyPanel, 100);
  }

  if (!form) return;

  function setLocationStatus(message, state = '') {
    if (!locationStatus) return;
    locationStatus.textContent = message;
    locationStatus.className = `location-status${state ? ` ${state}` : ''}`;
  }

  function selectedEmergencyType() {
    const selected = form.querySelector('input[name="emergency_type"]:checked');
    return selected ? selected.value : 'other';
  }

  // Geolocation handling
  if (locationButton) {
    locationButton.addEventListener('click', () => {
      if (!('geolocation' in navigator)) {
        coordinates = null;
        setLocationStatus('GPS is not available in this browser. Choose a city below.', 'error');
        showToast('GPS unavailable. Please select your city.', 'error');
        return;
      }

      locationButton.disabled = true;
      const strongEl = locationButton.querySelector('strong');
      if (strongEl) strongEl.textContent = 'Getting your location…';
      setLocationStatus('Waiting for browser location permission…');

      navigator.geolocation.getCurrentPosition(
        (position) => {
          coordinates = {
            lat: position.coords.latitude,
            lon: position.coords.longitude
          };
          if (citySelect) citySelect.value = '';
          setLocationStatus('GPS location captured successfully. Ready to search nearby directory.', 'success');
          if (strongEl) strongEl.textContent = `Location Captured (${coordinates.lat.toFixed(3)}, ${coordinates.lon.toFixed(3)})`;
          locationButton.disabled = false;
          showToast('GPS coordinates acquired.', 'success');
        },
        (error) => {
          coordinates = null;
          const messages = {
            1: 'Location permission was denied. Choose a city below instead.',
            2: 'Your location could not be determined. Choose a city below instead.',
            3: 'Location request timed out. Try again or choose a city.'
          };
          const msg = messages[error.code] || 'Unable to get location. Choose a city below.';
          setLocationStatus(msg, 'error');
          if (strongEl) strongEl.textContent = 'Use my current location';
          locationButton.disabled = false;
          showToast(msg, 'error');
        },
        { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 }
      );
    });
  }

  if (citySelect) {
    citySelect.addEventListener('change', () => {
      if (citySelect.value) {
        coordinates = null;
        setLocationStatus(`Manual location selected: ${citySelect.value}.`, 'success');
        const strongEl = locationButton?.querySelector('strong');
        if (strongEl) strongEl.textContent = 'Use my current location';
        showToast(`City selected: ${citySelect.value}`, 'info');
      }
    });
  }

  function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    return element;
  }

  function renderSkeletonLoading() {
    resultsGrid.replaceChildren();
    for (let i = 0; i < 4; i++) {
      const sk = createElement('div', 'skeleton-card');
      const b1 = createElement('div', 'skeleton-bar'); b1.style.width = '60%'; b1.style.height = '18px';
      const b2 = createElement('div', 'skeleton-bar'); b2.style.width = '40%';
      const b3 = createElement('div', 'skeleton-bar'); b3.style.width = '80%';
      const b4 = createElement('div', 'skeleton-bar'); b4.style.width = '30%'; b4.style.marginTop = '10px';
      sk.append(b1, b2, b3, b4);
      resultsGrid.appendChild(sk);
    }
  }

  function renderResults(payload) {
    resultsGrid.replaceChildren();
    const hospitals = Array.isArray(payload.results) ? payload.results : [];

    if (resultsCount) {
      resultsCount.textContent = `${hospitals.length} listed ${hospitals.length === 1 ? 'facility' : 'facilities'}`;
    }
    if (resultsSubtitle) {
      resultsSubtitle.textContent = payload.meta?.match_basis === 'straight_line_distance'
        ? 'Ordered by straight-line distance. Real-time road travel times may vary.'
        : 'Facilities listed for the selected city directory. (Distance calculation requires GPS).';
    }

    if (hospitals.length === 0) {
      const emptyBox = createElement('div', 'empty-results');
      emptyBox.innerHTML = `
        <div style="font-size: 28px; margin-bottom: 8px;">🏥</div>
        <strong>No hospital directory records found for this location.</strong>
        <p style="margin: 6px 0 0; color: var(--muted); font-size: 11px;">
          Try selecting a different nearby city or enable GPS location. In a life-threatening emergency, call <strong>112</strong> immediately.
        </p>
      `;
      resultsGrid.appendChild(emptyBox);
      return;
    }

    hospitals.forEach((hospital) => {
      const card = createElement('article', 'result-card');
      const top = createElement('div', 'result-card-top');
      const identity = createElement('div', '');
      identity.appendChild(createElement('h3', '', hospital.name));
      identity.appendChild(createElement('p', 'result-location', `${hospital.city}, ${hospital.district}`));
      top.append(identity, createElement('span', 'directory-chip', 'Public Directory'));

      const specialty = createElement('div', 'result-specialty', `Recorded Specialty: ${hospital.specialty || 'General / Multi-Specialty'}`);
      
      const distance = hospital.distance_km !== null && hospital.distance_km !== undefined
        ? createElement('div', 'result-distance', `📍 ${hospital.distance_km} km straight-line distance`)
        : createElement('div', 'result-distance', `📍 ${hospital.city} Municipal Area`);

      // Status pill & verification
      const verifyTag = createElement('div', 'result-caveat', hospital.verification_status || 'Verified Public Facility · Live Bed Unverified');

      const actions = createElement('div', 'result-actions');
      
      // Call link if available
      if (hospital.phone) {
        const phoneLink = createElement('a', 'result-directions', `📞 Call ${hospital.phone}`);
        phoneLink.href = `tel:${hospital.phone.replace(/[^0-9+]/g, '')}`;
        phoneLink.style.background = '#0e9b89';
        actions.appendChild(phoneLink);
      }

      const directions = createElement('a', 'result-directions', 'Directions ↗');
      directions.href = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(`${hospital.lat},${hospital.lon}`)}`;
      directions.target = '_blank';
      directions.rel = 'noopener noreferrer';
      actions.appendChild(directions);

      // ── Emergency SOS Admission Request Button ──
      const sosBtn = createElement('button', 'result-directions', '🚨 Request Emergency SOS');
      sosBtn.type = 'button';
      sosBtn.style.background = '#e63946';
      sosBtn.style.color = '#ffffff';
      sosBtn.style.fontWeight = 'bold';
      sosBtn.style.border = 'none';
      sosBtn.style.cursor = 'pointer';
      sosBtn.onclick = () => openSOSModal(hospital);
      actions.appendChild(sosBtn);

      card.append(top, specialty, distance, verifyTag, actions);
      resultsGrid.appendChild(card);
    });
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    if (!coordinates && (!citySelect || !citySelect.value)) {
      setLocationStatus('Share your current location or select a city to continue.', 'error');
      showToast('Please provide your location or select a city.', 'error');
      if (citySelect) citySelect.focus();
      return;
    }

    const params = new URLSearchParams({ emergency_type: selectedEmergencyType() });
    if (coordinates) {
      params.set('lat', String(coordinates.lat));
      params.set('lon', String(coordinates.lon));
    } else if (citySelect) {
      params.set('city', citySelect.value);
    }

    submitButton.disabled = true;
    const submitText = submitButton.querySelector('span:first-child');
    if (submitText) submitText.textContent = 'Searching directory…';
    
    resultsSection.hidden = false;
    resultsSection.removeAttribute('hidden');
    renderSkeletonLoading();
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

    try {
      const response = await fetch(`/api/emergency/hospitals?${params.toString()}`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        credentials: 'same-origin'
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || 'Hospital search failed. Please try again.');
      }

      renderResults(payload);
      showToast(`Found ${payload.results?.length || 0} matching facilities.`, 'success');
      resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (error) {
      setLocationStatus(error.message || 'Unable to search hospitals right now.', 'error');
      showToast(error.message || 'Hospital search failed.', 'error');
      resultsGrid.replaceChildren();
      const errBox = createElement('div', 'empty-results');
      errBox.innerHTML = `
        <div style="font-size: 28px; margin-bottom: 8px;">⚠️</div>
        <strong>${error.message || 'Hospital search failed.'}</strong>
        <p style="margin: 6px 0 0; color: var(--muted); font-size: 11px;">
          For immediate emergency assistance, call <strong>112</strong> or <strong>108</strong> directly.
        </p>
      `;
      resultsGrid.appendChild(errBox);
    } finally {
      submitButton.disabled = false;
      if (submitText) submitText.textContent = 'Find nearby hospitals';
    }
  });

  // ============================================================================
  // CITIZEN EMERGENCY SOS MODAL & REAL-TIME TRACKING
  // ============================================================================
  let activeTrackingInterval = null;

  function openSOSModal(hospital) {
    let modal = document.getElementById('aiis-sos-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'aiis-sos-modal';
      modal.className = 'aiis-sos-modal-overlay';
      modal.innerHTML = `
        <div class="aiis-sos-modal-content">
          <div class="aiis-sos-modal-header">
            <h3>🚨 Request Emergency Admission</h3>
            <button type="button" class="aiis-sos-close-btn" id="close-sos-modal-btn">✕</button>
          </div>
          <div class="aiis-sos-modal-body">
            <p style="margin-bottom: 12px; font-size: 13px; color: #4a5568;">
              Requesting emergency bed reservation and casualty dispatch at: <br/>
              <strong id="sos-modal-hosp-name" style="color: #1f4e79; font-size: 15px;"></strong>
            </p>
            <div style="display: grid; gap: 10px;">
              <div>
                <label style="display: block; font-size: 11px; font-weight: 700; color: #102544; margin-bottom: 4px;">Patient Name</label>
                <input type="text" id="sos-patient-name" value="Emergency Patient" style="width: 100%; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px;" />
              </div>
              <div>
                <label style="display: block; font-size: 11px; font-weight: 700; color: #102544; margin-bottom: 4px;">Contact Phone</label>
                <input type="tel" id="sos-patient-phone" value="+91 98765 43210" style="width: 100%; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px;" />
              </div>
              <div>
                <label style="display: block; font-size: 11px; font-weight: 700; color: #102544; margin-bottom: 4px;">Severity Level</label>
                <select id="sos-patient-severity" style="width: 100%; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px;">
                  <option value="CRITICAL">🔴 Critical (Immediate Resuscitation)</option>
                  <option value="HIGH" selected>🟠 High (Urgent Casualty Intake)</option>
                  <option value="MODERATE">🟡 Moderate (Acute Evaluation)</option>
                </select>
              </div>
              <div style="margin-top: 6px;">
                <button type="button" id="confirm-sos-submit-btn" style="width: 100%; padding: 12px; background: #e63946; color: white; border: none; border-radius: 8px; font-weight: 800; font-size: 14px; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px;">
                  <span>Transmit Emergency SOS &amp; Hold Bed</span> 🚨
                </button>
              </div>
            </div>
          </div>
        </div>
      `;
      document.body.appendChild(modal);

      document.getElementById('close-sos-modal-btn').onclick = () => {
        modal.style.display = 'none';
      };
    }

    document.getElementById('sos-modal-hosp-name').textContent = hospital.name;
    document.getElementById('confirm-sos-submit-btn').onclick = () => submitSOS(hospital);
    modal.style.display = 'flex';
  }

  async function submitSOS(hospital) {
    const btn = document.getElementById('confirm-sos-submit-btn');
    btn.disabled = true;
    btn.textContent = 'Transmitting Emergency SOS…';

    const patientName = document.getElementById('sos-patient-name').value.trim() || 'Emergency Patient';
    const contactPhone = document.getElementById('sos-patient-phone').value.trim() || '+919876543210';
    const severity = document.getElementById('sos-patient-severity').value || 'HIGH';
    const category = selectedEmergencyType();

    try {
      const resp = await fetch('/api/emergency/sos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hospital_id: hospital.id,
          target_hospital_id: hospital.id,
          patient_name: patientName,
          contact_phone: contactPhone,
          emergency_category: category,
          severity: severity
        })
      });

      const res = await resp.json();
      if (!resp.ok) {
        throw new Error(res.error?.message || res.message || 'Failed to submit SOS');
      }

      const sosData = res.data;
      document.getElementById('aiis-sos-modal').style.display = 'none';
      showToast('Emergency SOS Transmitted! Provisional Bed Allocated.', 'success');
      renderActiveTrackingCard(sosData, hospital);
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Transmit Emergency SOS & Hold Bed';
    }
  }

  function renderActiveTrackingCard(sosData, hospital) {
    let container = document.getElementById('aiis-active-sos-card');
    if (!container) {
      container = document.createElement('div');
      container.id = 'aiis-active-sos-card';
      resultsSection.prepend(container);
    }

    const reqId = sosData.id || sosData.request_id;
    const token = sosData.tracking_token;
    const arrivalOtp = sosData.arrival_otp || sosData.arrivalOtp || sosData.otp || '----';

    container.innerHTML = `
      <div style="background: linear-gradient(135deg, #102544 0%, #163a5f 100%); color: white; border: 2px solid #e63946; border-radius: 14px; padding: 22px; margin-bottom: 24px; box-shadow: 0 10px 30px rgba(230,57,70,0.25);">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; border-bottom: 1px solid rgba(255,255,255,0.15); padding-bottom: 14px; margin-bottom: 16px;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <span style="display: inline-block; width: 12px; height: 12px; background: #e63946; border-radius: 50%; box-shadow: 0 0 10px #e63946; animation: pulse 1.5s infinite;"></span>
            <strong style="font-size: 16px; letter-spacing: 0.5px;">ACTIVE EMERGENCY SOS TRACKING</strong>
          </div>
          <div style="font-family: monospace; font-size: 14px; background: rgba(255,255,255,0.12); padding: 4px 10px; border-radius: 6px;">
            ID: <span id="sos-card-req-id" style="color: #38d6b4; font-weight: bold;">${reqId}</span>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 18px;">
          <div>
            <div style="font-size: 11px; text-transform: uppercase; color: rgba(255,255,255,0.7); font-weight: 700;">Assigned Facility</div>
            <strong style="font-size: 15px; color: #ffffff; display: block; margin-top: 2px;">${hospital.name}</strong>
            <span style="font-size: 12px; color: rgba(255,255,255,0.8);">${hospital.city}, ${hospital.district || ''}</span>
          </div>
          <div>
            <div style="font-size: 11px; text-transform: uppercase; color: rgba(255,255,255,0.7); font-weight: 700;">Current Status</div>
            <span id="sos-live-status-badge" style="display: inline-block; margin-top: 4px; padding: 4px 12px; border-radius: 999px; background: #e63946; color: white; font-size: 12px; font-weight: 800;">
              ${sosData.status || 'REQUEST_SUBMITTED'}
            </span>
          </div>
          <div style="background: rgba(0,0,0,0.25); border: 1px dashed rgba(255,255,255,0.3); border-radius: 10px; padding: 12px; text-align: center;">
            <div style="font-size: 11px; text-transform: uppercase; color: #38d6b4; font-weight: 800;">Arrival Verification Code (OTP)</div>
            <div id="sos-arrival-otp-val" style="font-size: 32px; font-weight: 900; letter-spacing: 6px; color: #ffeb3b; margin: 4px 0;">${arrivalOtp}</div>
            <div style="font-size: 10px; color: rgba(255,255,255,0.75);">Present this 4-digit code to casualty desk upon arrival</div>
          </div>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; border-top: 1px solid rgba(255,255,255,0.15); padding-top: 14px;">
          <span style="font-size: 12px; color: rgba(255,255,255,0.75);" id="sos-poll-indicator">
            📡 Live Telemetry Active · Auto-refreshing status
          </span>
          <button type="button" id="sos-cancel-btn" style="padding: 8px 16px; background: transparent; border: 1px solid rgba(255,255,255,0.4); border-radius: 6px; color: #ff8a8a; font-weight: 700; font-size: 12px; cursor: pointer;">
            Cancel Emergency Request
          </button>
        </div>
      </div>
    `;

    container.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Cancel handler
    document.getElementById('sos-cancel-btn').onclick = async () => {
      if (!confirm('Are you sure you want to cancel this emergency request? Any held bed capacity will be released.')) return;
      try {
        const cancelUrl = token ? `/api/emergency/${reqId}/cancel?token=${encodeURIComponent(token)}` : `/api/emergency/${reqId}/cancel`;
        const cResp = await fetch(cancelUrl, { method: 'POST' });
        if (cResp.ok) {
          showToast('Emergency SOS cancelled. Held capacity released.', 'info');
          clearInterval(activeTrackingInterval);
          document.getElementById('sos-live-status-badge').textContent = 'CANCELLED';
          document.getElementById('sos-live-status-badge').style.background = '#64748b';
          document.getElementById('sos-poll-indicator').textContent = 'Request Cancelled';
          document.getElementById('sos-cancel-btn').style.display = 'none';
        }
      } catch (e) {
        showToast('Failed to cancel request.', 'error');
      }
    };

    // Polling status
    if (activeTrackingInterval) clearInterval(activeTrackingInterval);
    activeTrackingInterval = setInterval(async () => {
      try {
        const trackUrl = token ? `/api/emergency/${reqId}/track?token=${encodeURIComponent(token)}` : `/api/emergency/${reqId}/track`;
        const tResp = await fetch(trackUrl);
        if (tResp.ok) {
          const tData = await tResp.json();
          const curStatus = tData.data?.status || tData.status;
          const badge = document.getElementById('sos-live-status-badge');
          if (badge && curStatus) {
            badge.textContent = curStatus;
            if (curStatus === 'PATIENT_ARRIVED') {
              badge.textContent = 'PATIENT ARRIVED & ADMITTED';
              badge.style.background = '#0e9b89';
              document.getElementById('sos-poll-indicator').textContent = '✅ Patient Verified at Casualty Desk';
              document.getElementById('sos-cancel-btn').style.display = 'none';
              clearInterval(activeTrackingInterval);
            } else if (curStatus === 'CANCELLED' || curStatus === 'EXPIRED') {
              badge.textContent = curStatus;
              badge.style.background = '#64748b';
              clearInterval(activeTrackingInterval);
            }
          }
        }
      } catch (err) {
        // silent polling error
      }
    }, 4000);
  }
})();
