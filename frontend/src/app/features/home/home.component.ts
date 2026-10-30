import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-home',
  imports: [RouterLink],
  template: `
    <section class="hero page-container" aria-labelledby="hero-title">
      <div class="hero-copy">
        <p class="eyebrow">Clinical Evidence Verification Platform</p>
        <h1 id="hero-title">Verify Clinical Claims with <em>Research Evidence.</em></h1>
        <p class="hero-text">
          Explore biomedical research and clinical trial evidence with AI-assisted claim
          verification, bringing scientific literature and structured clinical study
          information into one workflow.
        </p>
        <div class="hero-actions">
          <a class="primary-button" routerLink="/verification">Verify a Claim <span aria-hidden="true">→</span></a>
          <a class="secondary-button" href="#how-it-works">Explore How It Works <span aria-hidden="true">↓</span></a>
        </div>
        <div class="source-indicators" aria-label="Research sources and model">
          <span><i class="indicator-dot pubmed"></i> PubMed</span>
          <span><i class="indicator-dot trials"></i> ClinicalTrials.gov</span>
          <span><i class="indicator-dot model"></i> BioBERT</span>
        </div>
      </div>
      <div class="research-visual" aria-label="Illustration of connected research evidence" role="img">
        <div class="visual-glow"></div>
        <svg viewBox="0 0 520 430" aria-hidden="true">
          <defs>
            <linearGradient id="cardBlue" x1="0" x2="1" y1="0" y2="1">
              <stop offset="0" stop-color="#f8fcff" />
              <stop offset="1" stop-color="#dceef8" />
            </linearGradient>
            <linearGradient id="cardTeal" x1="0" x2="1" y1="0" y2="1">
              <stop offset="0" stop-color="#ecfbfa" />
              <stop offset="1" stop-color="#ccebea" />
            </linearGradient>
          </defs>
          <path class="connection" d="M170 125 270 215M350 125 270 215M270 215l-35 105M270 215l105 105" />
          <circle class="node-halo" cx="270" cy="215" r="56" />
          <circle class="node-core" cx="270" cy="215" r="39" />
          <path class="shield" d="M270 190l18 7v13c0 12-8 22-18 27-10-5-18-15-18-27v-13l18-7Z" />
          <path class="shield-check" d="m259 211 8 8 15-17" />
          <g class="evidence-card card-one">
            <rect fill="url(#cardBlue)" height="104" rx="16" width="172" x="85" y="62" />
            <circle class="card-icon" cx="113" cy="91" r="13" />
            <path class="card-line" d="M137 88h82M137 99h56M103 112h106" />
            <text x="103" y="143">BIOMEDICAL LITERATURE</text>
          </g>
          <g class="evidence-card card-two">
            <rect fill="url(#cardTeal)" height="104" rx="16" width="172" x="263" y="62" />
            <circle class="card-icon teal" cx="291" cy="91" r="13" />
            <path class="card-line" d="M315 88h82M315 99h56M281 112h106" />
            <text x="281" y="143">CLINICAL TRIALS</text>
          </g>
          <g class="evidence-card card-three">
            <rect fill="#fff" height="82" rx="16" width="164" x="116" y="300" />
            <circle class="card-icon navy" cx="143" cy="328" r="13" />
            <path class="card-line" d="M167 325h82M167 336h55" />
            <text x="133" y="363">EVIDENCE CONTEXT</text>
          </g>
          <g class="evidence-card card-four">
            <rect fill="#fff" height="82" rx="16" width="164" x="292" y="300" />
            <circle class="card-icon blue" cx="319" cy="328" r="13" />
            <path class="card-line" d="M343 325h82M343 336h55" />
            <text x="309" y="363">MODEL OUTPUT</text>
          </g>
        </svg>
        <span class="visual-label label-top">Structured sources</span>
        <span class="visual-label label-bottom">Transparent workflow</span>
      </div>
    </section>

    <section class="workflow-section" id="how-it-works" aria-labelledby="workflow-title">
      <div class="page-container">
        <div class="section-heading">
          <p class="eyebrow">A clear research workflow</p>
          <h2 id="workflow-title">From question to context.</h2>
          <p>Each stage is designed to keep retrieved research visible alongside, but distinct from, the model's classification.</p>
        </div>
        <div class="steps-grid">
          <article class="step-card"><span class="step-number">01</span><div class="step-icon claim-icon" aria-hidden="true">⌁</div><h3>Submit a Clinical Claim</h3><p>Enter a biomedical or clinical research claim in plain language.</p></article>
          <article class="step-card"><span class="step-number">02</span><div class="step-icon search-icon" aria-hidden="true">⌕</div><h3>Retrieve Research Evidence</h3><p>Search PubMed and ClinicalTrials.gov for relevant articles and studies.</p></article>
          <article class="step-card"><span class="step-number">03</span><div class="step-icon analysis-icon" aria-hidden="true">◌</div><h3>Analyze with BioBERT</h3><p>Produce one research classification label while preserving the source context.</p></article>
        </div>
      </div>
    </section>

    <section class="features-section page-container" aria-labelledby="features-title">
      <div class="section-heading compact">
        <p class="eyebrow">Built for careful interpretation</p>
        <h2 id="features-title">Research tools with the source in view.</h2>
      </div>
      <div class="feature-grid">
        <article><div class="feature-icon literature" aria-hidden="true">▤</div><h3>Biomedical Literature Retrieval</h3><p>Find relevant PubMed articles and preserve their publication context and identifiers.</p></article>
        <article><div class="feature-icon trial" aria-hidden="true">＋</div><h3>Clinical Trial Discovery</h3><p>Surface structured ClinicalTrials.gov study information alongside literature evidence.</p></article>
        <article><div class="feature-icon classification" aria-hidden="true">◒</div><h3>AI-Assisted Classification</h3><p>Use the existing BioBERT service to classify claim-and-evidence context.</p></article>
        <article><div class="feature-icon transparency" aria-hidden="true">⌑</div><h3>Evidence Transparency</h3><p>Keep retrieved evidence, model scores and limitations separate in the workflow.</p></article>
      </div>
    </section>

    <section class="disclaimer-section page-container" aria-labelledby="disclaimer-title">
      <div class="disclaimer-card">
        <div class="disclaimer-mark" aria-hidden="true">i</div>
        <div><p class="eyebrow">Research prototype notice</p><h2 id="disclaimer-title">Interpret results with care.</h2><p>CliniFact is an experimental research prototype. Its predictions and model scores are not calibrated medical confidence and must not be used as a substitute for professional medical advice or clinical decision-making.</p></div>
      </div>
    </section>
  `,
  styles: `
    :host { display: block; }
    .page-container { margin: 0 auto; max-width: 80rem; padding-left: var(--page-gutter); padding-right: var(--page-gutter); }
    .hero { align-items: center; display: grid; gap: clamp(2rem, 6vw, 6rem); grid-template-columns: minmax(0, 1fr) minmax(24rem, .95fr); min-height: min(720px, calc(100vh - 5rem)); padding-bottom: var(--space-12); padding-top: clamp(4rem, 8vw, 7rem); }
    .eyebrow { color: var(--color-teal); font-size: .72rem; font-weight: 800; letter-spacing: .13em; margin: 0; text-transform: uppercase; }
    h1, h2, h3 { color: var(--color-navy); font-family: var(--font-display); }
    h1 { font-size: clamp(2.8rem, 5.2vw, 5.2rem); letter-spacing: -.075em; line-height: .98; margin: var(--space-4) 0 var(--space-6); max-width: 11ch; }
    h1 em { color: var(--color-blue); font-style: normal; }
    .hero-text { color: var(--color-muted); font-size: clamp(1rem, 1.4vw, 1.15rem); line-height: 1.75; margin: 0; max-width: 38rem; }
    .hero-actions { align-items: center; display: flex; flex-wrap: wrap; gap: var(--space-3); margin-top: var(--space-8); }
    .primary-button, .secondary-button { align-items: center; border-radius: var(--radius-md); display: inline-flex; font-weight: 700; gap: var(--space-3); padding: .9rem 1.2rem; text-decoration: none; }
    .primary-button { background: var(--color-navy); color: var(--color-white); }
    .primary-button:hover { background: var(--color-blue); transform: translateY(-2px); }
    .secondary-button { border: 1px solid var(--color-border); color: var(--color-navy); }
    .secondary-button:hover { background: var(--color-blue-soft); border-color: #b6d2e7; }
    .source-indicators { align-items: center; color: var(--color-muted); display: flex; flex-wrap: wrap; font-size: .78rem; gap: var(--space-4); margin-top: var(--space-8); }
    .source-indicators span { align-items: center; display: inline-flex; gap: .4rem; }
    .indicator-dot { background: var(--color-blue); border-radius: 50%; display: inline-block; height: .42rem; width: .42rem; }
    .indicator-dot.trials { background: var(--color-teal); }
    .indicator-dot.model { background: #8a75c5; }
    .research-visual { min-height: 28rem; position: relative; }
    .research-visual svg { height: auto; overflow: visible; position: relative; width: 100%; z-index: 1; }
    .visual-glow { background: #dceff5; border-radius: 50%; filter: blur(1px); height: 18rem; left: 18%; opacity: .7; position: absolute; top: 16%; width: 18rem; }
    .connection { fill: none; stroke: #9dc9d6; stroke-dasharray: 4 7; stroke-width: 2; }
    .node-halo { fill: #e7f5f5; stroke: #a4d5d4; stroke-width: 1; }
    .node-core { fill: var(--color-teal); }
    .shield, .shield-check { fill: none; stroke: #fff; stroke-linecap: round; stroke-linejoin: round; stroke-width: 2; }
    .evidence-card rect { filter: drop-shadow(0 10px 14px rgb(16 42 67 / 10%)); stroke: rgb(255 255 255 / 70%); stroke-width: 1; }
    .card-icon { fill: #5da7c0; }
    .card-icon.teal { fill: var(--color-teal); }
    .card-icon.navy { fill: var(--color-navy); }
    .card-icon.blue { fill: var(--color-blue); }
    .card-line { fill: none; stroke: #88a6b8; stroke-linecap: round; stroke-width: 3; }
    .evidence-card text { fill: #60758a; font-size: 9px; font-weight: 800; letter-spacing: 1px; }
    .visual-label { background: rgb(255 255 255 / 90%); border: 1px solid var(--color-border); border-radius: 99px; box-shadow: var(--shadow-card); color: var(--color-muted); font-size: .7rem; font-weight: 700; padding: .5rem .75rem; position: absolute; z-index: 2; }
    .label-top { right: 2%; top: 12%; }
    .label-bottom { bottom: 4%; left: 5%; }
    .workflow-section { background: var(--color-surface); border-bottom: 1px solid var(--color-border); border-top: 1px solid var(--color-border); padding: clamp(4rem, 8vw, 7rem) 0; }
    .section-heading { max-width: 38rem; }
    .section-heading h2 { font-size: clamp(2rem, 4vw, 3.4rem); letter-spacing: -.06em; line-height: 1.05; margin: var(--space-4) 0; }
    .section-heading > p:last-child { color: var(--color-muted); line-height: 1.7; margin: 0; }
    .steps-grid, .feature-grid { display: grid; gap: var(--space-4); grid-template-columns: repeat(3, 1fr); margin-top: var(--space-12); }
    .step-card { border-top: 2px solid var(--color-blue); padding: var(--space-6) var(--space-4) 0 0; position: relative; }
    .step-number { color: var(--color-blue); font-size: .75rem; font-weight: 800; letter-spacing: .1em; }
    .step-icon, .feature-icon { align-items: center; background: var(--color-blue-soft); border-radius: 50%; color: var(--color-blue); display: flex; font-size: 1.7rem; height: 3.25rem; justify-content: center; margin: var(--space-6) 0 var(--space-4); width: 3.25rem; }
    .search-icon { background: #e4f5f3; color: var(--color-teal); }
    .analysis-icon { background: #eeeafa; color: #806bb8; }
    .step-card h3, .feature-grid h3 { font-size: 1.1rem; margin: 0 0 var(--space-3); }
    .step-card p, .feature-grid p { color: var(--color-muted); line-height: 1.6; margin: 0; }
    .features-section { padding-bottom: clamp(4rem, 8vw, 7rem); padding-top: clamp(4rem, 8vw, 7rem); }
    .section-heading.compact { max-width: 42rem; }
    .feature-grid { grid-template-columns: repeat(4, 1fr); margin-top: var(--space-8); }
    .feature-grid article { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); box-shadow: 0 4px 18px rgb(16 42 67 / 4%); padding: var(--space-6); }
    .feature-icon { border-radius: var(--radius-md); font-size: 1.4rem; margin-top: 0; }
    .feature-icon.trial { background: #e4f5f3; color: var(--color-teal); }
    .feature-icon.classification { background: #eeeafa; color: #806bb8; }
    .feature-icon.transparency { background: #fff2df; color: #b67a23; }
    .disclaimer-section { padding-bottom: clamp(4rem, 8vw, 7rem); }
    .disclaimer-card { align-items: flex-start; background: #eaf3f8; border: 1px solid #cfe2ee; border-radius: var(--radius-lg); display: flex; gap: var(--space-6); padding: clamp(1.5rem, 4vw, 2.5rem); }
    .disclaimer-mark { align-items: center; background: var(--color-blue); border-radius: 50%; color: var(--color-white); display: flex; flex: 0 0 2rem; font-weight: 800; height: 2rem; justify-content: center; }
    .disclaimer-card h2 { font-size: 1.5rem; margin: var(--space-3) 0; }
    .disclaimer-card p:last-child { color: var(--color-ink); line-height: 1.65; margin: 0; max-width: 62rem; }
    @media (max-width: 900px) { .hero { grid-template-columns: 1fr; } .research-visual { max-width: 38rem; } .feature-grid { grid-template-columns: repeat(2, 1fr); } }
    @media (max-width: 640px) { .hero { min-height: auto; padding-top: 3.5rem; } .research-visual { min-height: 22rem; } .steps-grid, .feature-grid { grid-template-columns: 1fr; } .source-indicators { gap: var(--space-3); } .disclaimer-card { flex-direction: column; gap: var(--space-3); } }
    @media (prefers-reduced-motion: reduce) { .primary-button, .secondary-button { transition: none; } }
  `,
})
export class HomeComponent {}
