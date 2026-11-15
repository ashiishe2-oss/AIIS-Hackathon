/* ============================================================
   AIIS – main.js  |  Search, Filter, AI Predictor
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {

  /* ── Search & Filter ── */
  const searchInput    = document.getElementById('searchInput');
  const specialtyFilter= document.getElementById('specialtyFilter');
  const cityFilter     = document.getElementById('cityFilter');
  const searchBtn      = document.getElementById('searchBtn');
  const hospitalGrid   = document.getElementById('hospitalGrid');
  const noResults      = document.getElementById('noResults');

  if (searchBtn) {
    searchBtn.addEventListener('click', fetchHospitals);
    searchInput && searchInput.addEventListener('keydown', e => e.key === 'Enter' && fetchHospitals());
  }

  async function fetchHospitals() {
    const query     = searchInput     ? searchInput.value.trim()      : '';
    const specialty = specialtyFilter ? specialtyFilter.value         : '';
    const city      = cityFilter      ? cityFilter.value              : '';

    const params = new URLSearchParams();
    if (query)     params.set('query',     query);
    if (specialty) params.set('specialty', specialty);
    if (city)      params.set('city',      city);

    try {
      const res   = await fetch(`/api/search?${params.toString()}`);
      const data  = await res.json();
      renderHospitals(data);
    } catch (err) {
      console.error('Search error:', err);
    }
  }

  function renderHospitals(hospitals) {
    if (!hospitalGrid) return;
    hospitalGrid.innerHTML = '';

    if (hospitals.length === 0) {
      noResults && noResults.classList.remove('hidden');
      return;
    }
    noResults && noResults.classList.add('hidden');

    hospitals.forEach(h => {
      const ratingPct = Math.round((h.rating / 5) * 100);
      const card = document.createElement('div');
      card.className = 'hospital-card';
      card.innerHTML = `
        <div class="card-header">
          <div class="card-icon">🏥</div>
          <div class="card-score">
            <span class="score-badge">${h.score}</span>
            <span class="score-label">AI Score</span>
          </div>
        </div>
        <h3 class="card-name">${h.name}</h3>
        <p class="card-specialty">${h.specialty}</p>
        <p class="card-city">📍 ${h.city}</p>
        <div class="card-meta">
          <span>👨‍⚕️ ${h.num_doctors} Doctors</span>
          <span>🛏 ${h.num_beds} Beds</span>
          <span>⏱ ${h.avg_wait_time} min wait</span>
        </div>
        <div class="rating-bar">
          <div class="rating-fill" style="width: ${ratingPct}%"></div>
        </div>
        <p class="rating-text">⭐ ${h.rating} / 5.0</p>
        <a href="/hospital/${h.id}" class="btn-card">View Details →</a>
      `;
      hospitalGrid.appendChild(card);
    });
  }

  /* ── AI Predictor ── */
  const predictBtn       = document.getElementById('predictBtn');
  const predictionResult = document.getElementById('predictionResult');
  const predScore        = document.getElementById('predScore');

  if (predictBtn) {
    predictBtn.addEventListener('click', async () => {
      const num_doctors  = parseFloat(document.getElementById('numDoctors').value) || 0;
      const num_beds     = parseFloat(document.getElementById('numBeds').value)    || 0;
      const avg_wait_time= parseFloat(document.getElementById('avgWait').value)    || 0;
      const rating       = parseFloat(document.getElementById('rating').value)     || 0;

      predictBtn.textContent = 'Predicting…';
      predictBtn.disabled    = true;

      try {
        const res  = await fetch('/api/predict', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ num_doctors, num_beds, avg_wait_time, rating })
        });
        const data = await res.json();

        if (data.error) {
          predScore.textContent = 'N/A';
          alert(data.error);
        } else {
          predScore.textContent = data.predicted_score;
          predictionResult.classList.remove('hidden');
        }
      } catch (err) {
        console.error('Prediction error:', err);
      } finally {
        predictBtn.textContent = 'Predict Score';
        predictBtn.disabled    = false;
      }
    });
  }

  /* ── Animate rating bars on page load ── */
  setTimeout(() => {
    document.querySelectorAll('.rating-fill').forEach(bar => {
      const target = bar.style.width;
      bar.style.width = '0%';
      requestAnimationFrame(() => { bar.style.width = target; });
    });
  }, 200);

});
