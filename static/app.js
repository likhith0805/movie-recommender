function el(id) {
  return document.getElementById(id);
}

async function apiJson(url, opts = {}) {
  const res = await fetch(url, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(opts.headers || {}),
    },
    credentials: "same-origin",
  });

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const message = data && data.error ? data.error : `Request failed (${res.status})`;
    throw new Error(message);
  }
  return data;
}

function posterUrl(title) {
  const safe = encodeURIComponent(title || "Poster");
  return `https://via.placeholder.com/300x450?text=${safe}`;
}

function ratingLabel(movie) {
  const r = movie.user_rating ?? movie.avg_rating;
  if (r == null) return "Not rated";
  return `Rating: ${Number(r).toFixed(1)}/5`;
}

function ratingLabelInt(movie) {
  const r = movie.user_rating ?? movie.avg_rating;
  if (r == null) return "Not rated";
  return `Rating: ${Math.round(Number(r))}/5`;
}

function movieCardHtml(movie, { showWhy = false, showFeedback = false, detailsLink = true } = {}) {
  const recWhy = movie.why ? `<div class="small text-white-50 mt-2">${movie.why}</div>` : "";
  const feedback =
    showFeedback
      ? `
    <div class="d-flex gap-2 mt-2">
      <button class="btn btn-sm btn-success" data-feedback="like" data-movie-id="${movie.movie_id ?? movie.id}">Like</button>
      <button class="btn btn-sm btn-outline-danger" data-feedback="dislike" data-movie-id="${movie.movie_id ?? movie.id}">Dislike</button>
    </div>
    <div class="small text-white-50 mt-2" data-movie-rating-note></div>
    `
      : "";

  const id = movie.movie_id ?? movie.id;
  const title = movie.title ?? "";
  const genre = movie.genre ?? "";

  const rating = movie.user_rating ?? movie.avg_rating;
  const ratingText = rating == null ? "Not rated" : `Rating: ${Number(rating).toFixed(1)}/5`;

  const poster = movie.poster_url ? movie.poster_url : posterUrl(title);

  const viewBtn = detailsLink
    ? `<a class="btn btn-sm btn-outline-light" href="/movie/${id}">View details</a>`
    : "";

  return `
    <div class="col">
      <div class="card h-100 app-card">
        <img src="${poster}" class="card-img-top poster-img" alt="Poster"/>
        <div class="card-body">
          <div class="d-flex justify-content-between align-items-start gap-2">
            <div>
              <h3 class="h6 mb-1">${title}</h3>
              <div class="small text-white-50">${genre}</div>
            </div>
            <div class="text-end">
              <div class="small fw-bold">${ratingText}</div>
            </div>
          </div>
          ${recWhy}
          ${showWhy ? recWhy : ""}
          <div class="mt-3 d-flex gap-2 align-items-center">
            ${viewBtn}
            ${showFeedback ? feedback : ""}
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderGrid(gridEl, moviesHtml) {
  gridEl.innerHTML = moviesHtml.join("");
}

function parseUserIdsInput(text) {
  if (!text) return [];
  const parts = text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const ids = [];
  for (const p of parts) {
    const n = Number(p);
    if (Number.isFinite(n) && Number.isInteger(n) && n > 0) ids.push(n);
  }
  // Deduplicate
  return Array.from(new Set(ids));
}

function hideIfExists(id, condition) {
  const node = el(id);
  if (!node) return;
  node.classList.toggle("d-none", !!condition);
}

async function handleFeedback(movieId, feedback) {
  await apiJson("/api/feedback", {
    method: "POST",
    body: JSON.stringify({ movie_id: movieId, feedback }),
  });
}

async function handleNumericRating(movieId, rating) {
  await apiJson("/api/ratings", {
    method: "POST",
    body: JSON.stringify({ movie_id: movieId, rating }),
  });
}

async function setMeState() {
  const meLabel = el("meLabel");
  const meSmall = el("meSmallLabel");
  const logoutBtn = el("logoutBtn");

  let me = null;
  try {
    me = await apiJson("/api/me", { method: "GET" });
  } catch (e) {
    // ignore
  }

  if (!me || !me.logged_in) {
    if (meLabel) meLabel.textContent = "";
    if (meSmall) meSmall.textContent = "";
    if (logoutBtn) logoutBtn.classList.add("d-none");
    return null;
  }

  if (meLabel) meLabel.textContent = `Hi, ${me.username}`;
  if (meSmall) meSmall.textContent = `Signed in as ${me.username} (user ${me.user_id})`;
  if (logoutBtn) logoutBtn.classList.remove("d-none");
  return me;
}

async function initBrowsePage() {
  const moviesGrid = el("moviesGrid");
  const loading = el("moviesLoading");
  const error = el("moviesError");

  const searchInput = el("searchInput");
  const genreInput = el("genreInput");
  const searchBtn = el("searchBtn");
  const refreshBtn = el("refreshMoviesBtn");

  async function load() {
    const query = searchInput.value.trim();
    const genre = genreInput.value.trim();

    error.classList.add("d-none");
    loading.classList.remove("d-none");

    const params = new URLSearchParams();
    if (query) params.set("query", query);
    if (genre) params.set("genre", genre);
    params.set("limit", "24");

    try {
      const data = await apiJson(`/api/movies?${params.toString()}`, { method: "GET" });
      const movies = data.movies || [];
      moviesGrid.innerHTML = movies
        .map((m) => {
          const id = m.id;
          const poster = posterUrl(m.title);
          const rating = m.user_rating ?? m.avg_rating;
          const ratingText = rating == null ? "Not rated" : `Rating: ${Number(rating).toFixed(1)}/5`;
          return `
            <div class="col">
              <div class="card h-100 app-card">
                <img src="${poster}" class="card-img-top poster-img" alt="Poster"/>
                <div class="card-body">
                  <h3 class="h6 mb-1">${m.title}</h3>
                  <div class="small text-white-50 mb-2">${m.genre}</div>
                  <div class="small fw-bold mb-3">${ratingText}</div>
                  <a class="btn btn-sm btn-outline-light" href="/movie/${id}">View details</a>
                </div>
              </div>
            </div>
          `;
        })
        .join("");
    } catch (e) {
      error.textContent = e.message || "Failed to load movies.";
      error.classList.remove("d-none");
    } finally {
      loading.classList.add("d-none");
    }
  }

  searchBtn.addEventListener("click", load);
  refreshBtn.addEventListener("click", load);
  load();
}

async function initMovieDetailsPage() {
  const movieId = window.MOVIE_ID;
  const movieLoading = el("movieLoading");
  const movieError = el("movieError");
  const section = el("movieDetailsSection");

  const moviePoster = el("moviePoster");
  const movieTitle = el("movieTitle");
  const movieGenre = el("movieGenre");
  const yourRatingLabel = el("yourRatingLabel");
  const likeBtn = el("likeBtn");
  const dislikeBtn = el("dislikeBtn");

  const personalGrid = el("personalRecsGrid");
  const personalLoading = el("personalRecsLoading");
  const personalError = el("personalRecsError");

  function setLoading(isLoading) {
    movieLoading.classList.toggle("d-none", !isLoading);
    if (isLoading) section.classList.add("d-none");
  }

  function posterFor(title) {
    return posterUrl(title);
  }

  async function loadMovie() {
    setLoading(true);
    movieError.classList.add("d-none");
    const data = await apiJson(`/api/movies/${movieId}`, { method: "GET" });
    const m = data.movie;
    moviePoster.src = posterFor(m.title);
    movieTitle.textContent = m.title;
    movieGenre.textContent = m.genre;

    if (m.user_rating == null) yourRatingLabel.textContent = "Not rated";
    else yourRatingLabel.textContent = `You rated: ${m.user_rating}/5`;

    section.classList.remove("d-none");
  }

  async function loadRecs() {
    personalLoading.classList.remove("d-none");
    personalError.classList.add("d-none");
    personalGrid.innerHTML = "";

    try {
      const data = await apiJson("/api/recommendations", {
        method: "POST",
        body: JSON.stringify({}),
      });

      const recs = data.recommendations || [];
      personalGrid.innerHTML = recs
        .map((r) => {
          const poster = posterUrl(r.title);
          const id = r.movie_id;
          const rating = r.avg_rating;
          const ratingText = rating == null ? "Rating: N/A" : `Rating: ${Number(rating).toFixed(1)}/5`;
          return `
            <div class="col">
              <div class="card h-100 app-card">
                <img src="${poster}" class="card-img-top poster-img" alt="Poster"/>
                <div class="card-body">
                  <h3 class="h6 mb-1">${r.title}</h3>
                  <div class="small text-white-50 mb-2">${r.genre}</div>
                  <div class="small text-white-50">${ratingText}</div>
                  <div class="small text-white-50">${Number(r.score).toFixed(2)} match score</div>
                  <div class="small text-white-50 mt-2"><b>Why recommended:</b> ${r.why || ""}</div>
                  <div class="d-flex gap-2 mt-3 align-items-center">
                    <a class="btn btn-sm btn-outline-light" href="/movie/${id}">View</a>
                    <button class="btn btn-sm btn-success" data-feedback="like" data-movie-id="${id}">Like</button>
                    <button class="btn btn-sm btn-outline-danger" data-feedback="dislike" data-movie-id="${id}">Dislike</button>
                  </div>
                </div>
              </div>
            </div>
          `;
        })
        .join("");
    } catch (e) {
      personalError.textContent = e.message || "Failed to load recommendations.";
      personalError.classList.remove("d-none");
    } finally {
      personalLoading.classList.add("d-none");
    }
  }

  async function updateRatingFromButton(target, feedbackType) {
    likeBtn.disabled = true;
    dislikeBtn.disabled = true;
    try {
      await handleFeedback(movieId, feedbackType);
      await loadMovie();
      await loadRecs();
    } catch (e) {
      alert(e.message || "Failed to submit feedback.");
    } finally {
      likeBtn.disabled = false;
      dislikeBtn.disabled = false;
    }
  }

  likeBtn.addEventListener("click", () => updateRatingFromButton(likeBtn, "like"));
  dislikeBtn.addEventListener("click", () => updateRatingFromButton(dislikeBtn, "dislike"));

  // Numeric rating buttons.
  document.querySelectorAll("[data-rating]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const rating = Number(btn.getAttribute("data-rating"));
      try {
        await handleNumericRating(movieId, rating);
        await loadMovie();
        await loadRecs();
      } catch (e) {
        alert(e.message || "Failed to submit rating.");
      }
    });
  });

  // Feedback on recommended cards.
  personalGrid.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const movieIdAttr = target.getAttribute("data-movie-id");
    const feedback = target.getAttribute("data-feedback");
    if (!movieIdAttr || !feedback) return;

    try {
      await handleFeedback(Number(movieIdAttr), feedback);
      await loadRecs();
    } catch (e) {
      alert(e.message || "Failed to submit feedback.");
    }
  });

  // Initial load
  try {
    await loadMovie();
    await loadRecs();
  } catch (e) {
    movieError.textContent = e.message || "Failed to load movie.";
    movieError.classList.remove("d-none");
    movieLoading.classList.add("d-none");
  } finally {
    movieLoading.classList.add("d-none");
  }
}

async function initDashboardPage() {
  const personalGrid = el("personalRecsGrid");
  const personalLoading = el("personalRecsLoading");
  const personalError = el("personalRecsError");

  const groupInput = el("groupUserIdsInput");
  const groupBtn = el("groupRecBtn");
  const useMeBtn = el("useMeAsGroupBtn");
  const groupGrid = el("groupRecsGrid");
  const groupLoading = el("groupRecsLoading");
  const groupError = el("groupRecsError");

  const chatInput = el("chatInput");
  const chatSendBtn = el("chatSendBtn");
  const chatReply = el("chatReply");
  const chatAlert = el("chatAlert");
  const chatRecsGrid = el("chatRecsGrid");

  async function renderRecs(targetGrid, recs) {
    targetGrid.innerHTML = (recs || [])
      .map((r) => {
        const poster = posterUrl(r.title);
        const id = r.movie_id;
        const rating = r.avg_rating;
        const ratingText = rating == null ? "Rating: N/A" : `Rating: ${Number(rating).toFixed(1)}/5`;
        return `
          <div class="col">
            <div class="card h-100 app-card">
              <img src="${poster}" class="card-img-top poster-img" alt="Poster"/>
              <div class="card-body">
                <h3 class="h6 mb-1">${r.title}</h3>
                <div class="small text-white-50 mb-2">${r.genre}</div>
                <div class="small text-white-50">${ratingText}</div>
                <div class="small text-white-50">${Number(r.score).toFixed(2)} match score</div>
                <div class="small text-white-50 mt-2"><b>Why recommended:</b> ${r.why || ""}</div>
                <div class="d-flex gap-2 mt-3 align-items-center">
                  <a class="btn btn-sm btn-outline-light" href="/movie/${id}">View</a>
                  <button class="btn btn-sm btn-success" data-feedback="like" data-movie-id="${id}">Like</button>
                  <button class="btn btn-sm btn-outline-danger" data-feedback="dislike" data-movie-id="${id}">Dislike</button>
                </div>
              </div>
            </div>
          </div>
        `;
      })
      .join("");
  }

  async function loadPersonal() {
    personalLoading.classList.remove("d-none");
    personalError.classList.add("d-none");
    try {
      const data = await apiJson("/api/recommendations", {
        method: "POST",
        body: JSON.stringify({}),
      });
      await renderRecs(personalGrid, data.recommendations);
    } catch (e) {
      personalError.textContent = e.message || "Failed to load personal recommendations.";
      personalError.classList.remove("d-none");
    } finally {
      personalLoading.classList.add("d-none");
    }
  }

  async function loadGroup() {
    const ids = parseUserIdsInput(groupInput.value);
    groupError.classList.add("d-none");
    groupLoading.classList.remove("d-none");
    groupGrid.innerHTML = "";

    if (!ids.length) {
      groupLoading.classList.add("d-none");
      groupError.textContent = "Please enter at least one valid user id.";
      groupError.classList.remove("d-none");
      return;
    }

    try {
      const data = await apiJson("/api/recommendations", {
        method: "POST",
        body: JSON.stringify({ user_ids: ids }),
      });
      await renderRecs(groupGrid, data.recommendations);
    } catch (e) {
      groupError.textContent = e.message || "Failed to load group recommendations.";
      groupError.classList.remove("d-none");
    } finally {
      groupLoading.classList.add("d-none");
    }
  }

  // Like/dislike feedback in both grids.
  async function onFeedbackClick(event) {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const movieIdAttr = target.getAttribute("data-movie-id");
    const feedback = target.getAttribute("data-feedback");
    if (!movieIdAttr || !feedback) return;
    try {
      await handleFeedback(Number(movieIdAttr), feedback);
      // Refresh both sections so feedback is reflected quickly.
      await loadPersonal();
      await loadGroup();
    } catch (e) {
      alert(e.message || "Failed to submit feedback.");
    }
  }

  personalGrid.addEventListener("click", onFeedbackClick);
  groupGrid.addEventListener("click", onFeedbackClick);

  groupBtn.addEventListener("click", loadGroup);
  useMeBtn.addEventListener("click", async () => {
    const me = await setMeState();
    if (!me) return;
    groupInput.value = String(me.user_id);
    await loadGroup();
  });

  // Chatbot
  chatSendBtn.addEventListener("click", async () => {
    const query = chatInput.value.trim();
    if (!query) return;
    chatAlert.classList.add("d-none");
    chatReply.textContent = "";
    chatRecsGrid.innerHTML = "";

    try {
      // Provide user_ids if the group input looks valid; chatbot can also extract ids from the text.
      const ids = parseUserIdsInput(groupInput.value);
      const data = await apiJson("/api/chatbot", {
        method: "POST",
        body: JSON.stringify({ query, user_ids: ids.length ? ids : null }),
      });

      chatReply.textContent = data.reply || "";
      await renderRecs(chatRecsGrid, data.recommendations);
    } catch (e) {
      chatAlert.textContent = e.message || "Chatbot request failed.";
      chatAlert.classList.remove("d-none");
    }
  });

  await setMeState();
  await loadPersonal();
}

function hookLogout() {
  const logoutBtn = el("logoutBtn");
  if (!logoutBtn) return;
  logoutBtn.addEventListener("click", async () => {
    try {
      await apiJson("/api/auth/logout", { method: "POST", body: JSON.stringify({}) });
    } finally {
      window.location.href = "/login";
    }
  });
}

async function main() {
  hookLogout();
  await setMeState();

  const page = window.APP_PAGE;
  if (page === "browse") return initBrowsePage();
  if (page === "movie_details") return initMovieDetailsPage();
  if (page === "dashboard") return initDashboardPage();
  if (page === "login") return initLoginPage();
}

document.addEventListener("DOMContentLoaded", main);

function showAuthAlert(message) {
  const alertEl = el("authAlert");
  if (!alertEl) return;
  alertEl.textContent = message || "";
  alertEl.classList.toggle("d-none", !message);
}

function getFormValues(formEl) {
  const username = formEl.querySelector('input[name="username"]').value.trim();
  const password = formEl.querySelector('input[name="password"]').value;
  return { username, password };
}

async function initLoginPage() {
  const loginForm = el("loginForm");
  const signupForm = el("signupForm");
  if (!loginForm || !signupForm) return;

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    showAuthAlert("");
    const { username, password } = getFormValues(loginForm);
    try {
      const data = await apiJson("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      if (data && data.success) window.location.href = "/browse";
    } catch (e) {
      showAuthAlert(e.message || "Login failed.");
    }
  });

  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    showAuthAlert("");
    const { username, password } = getFormValues(signupForm);
    try {
      const data = await apiJson("/api/auth/signup", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      if (data && data.success) window.location.href = "/browse";
    } catch (e) {
      showAuthAlert(e.message || "Signup failed.");
    }
  });
}

