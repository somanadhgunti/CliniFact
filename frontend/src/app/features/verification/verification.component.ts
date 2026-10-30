import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  ValidatorFn,
  Validators,
} from '@angular/forms';
import { ClinifactApiService } from '../../core/services/clinifact-api.service';
import {
  EvidenceItem,
  PredictionLabel,
  VerificationResponse,
} from '../../models/verification.models';

const CLAIM_MAX_LENGTH = 4000;
const MIN_EVIDENCE_ITEMS = 1;
const MAX_EVIDENCE_ITEMS = 20;
const DEFAULT_EVIDENCE_ITEMS = 5;

const nonWhitespaceValidator: ValidatorFn = (
  control: AbstractControl,
): ValidationErrors | null => {
  const value = typeof control.value === 'string' ? control.value : '';
  return value.trim().length > 0 ? null : { whitespace: true };
};

@Component({
  selector: 'app-verification',
  imports: [ReactiveFormsModule],
  template: `
    <main class="verification-page">
      <section class="page-intro page-container" aria-labelledby="verification-title">
        <p class="eyebrow">Verification workspace</p>
        <h1 id="verification-title">Verify a Clinical Claim</h1>
        <p>Submit a biomedical or clinical research claim to explore relevant scientific literature and clinical trial evidence.</p>
      </section>

      <section class="workspace page-container" aria-label="Clinical claim verification">
        <form class="claim-card" [formGroup]="verificationForm" (ngSubmit)="submitClaim()" novalidate>
          <div class="card-heading">
            <div>
              <p class="eyebrow">Start with a research question</p>
              <h2>What would you like to explore?</h2>
            </div>
            <span class="step-badge">01 <span>of 01</span></span>
          </div>

          <div class="field-group">
            <label for="claim">Clinical claim</label>
            <textarea
              id="claim"
              formControlName="claim"
              rows="8"
              [attr.maxlength]="claimMaxLength"
              placeholder="Example: Regular aerobic exercise is associated with improved glycemic control in adults with type 2 diabetes."
              [attr.aria-invalid]="claimInvalid"
              [attr.aria-describedby]="claimInvalid ? 'claim-help claim-error' : 'claim-help'"
            ></textarea>
            <div class="field-meta">
              <span id="claim-help">Use a specific biomedical or clinical research statement.</span>
              <span [class.limit-near]="claimLength > claimMaxLength * 0.9">{{ claimLength }} / {{ claimMaxLength }}</span>
            </div>
            @if (claimInvalid) {
              <p class="field-error" id="claim-error" role="alert">
                @if (claimControl.hasError('required') || claimControl.hasError('whitespace')) {
                  Enter a clinical claim before continuing.
                } @else if (claimControl.hasError('maxlength')) {
                  Claims must be {{ claimMaxLength }} characters or fewer.
                }
              </p>
            }
          </div>

          <div class="form-controls">
            <div class="field-group evidence-field">
              <label for="evidence-count">Maximum evidence results</label>
              <select id="evidence-count" formControlName="maxEvidenceItems" [attr.aria-invalid]="evidenceInvalid">
                @for (count of evidenceOptions; track count) {
                  <option [ngValue]="count">{{ count }} {{ count === 1 ? 'result' : 'results' }}</option>
                }
              </select>
              @if (evidenceInvalid) {
                <p class="field-error" role="alert">Choose between {{ minEvidenceItems }} and {{ maxEvidenceItems }} results.</p>
              } @else {
                <p class="field-hint">Results are combined across PubMed and ClinicalTrials.gov.</p>
              }
            </div>
            <div class="form-actions">
              <button class="clear-button" type="button" (click)="clearForm()">Clear</button>
              <button class="primary-button" type="submit" [disabled]="verificationForm.invalid || isLoading()">
                @if (isLoading()) {
                  <span class="spinner" aria-hidden="true"></span> Verifying...
                } @else {
                  Verify Claim <span aria-hidden="true">→</span>
                }
              </button>
            </div>
          </div>
          @if (isLoading()) {
            <p class="form-status loading-status" aria-live="polite">
              <span class="status-dot" aria-hidden="true"></span>
              Retrieving research evidence and analyzing the clinical claim...
            </p>
          } @else if (errorMessage()) {
            <p class="form-status error-status" role="alert" aria-live="assertive">{{ errorMessage() }}</p>
          } @else if (verificationResponse()) {
            <p class="form-status success-status" role="status" aria-live="polite">
              Verification completed. Retrieved evidence and model output are ready for review.
            </p>
          } @else {
            <p class="form-status" aria-live="polite">Your claim will be sent to the CliniFact research API for verification.</p>
          }
        </form>

        <aside class="info-panel" aria-labelledby="workflow-title">
          <div class="panel-topline"><span class="pulse-dot"></span><span>How the workflow works</span></div>
          <h2 id="workflow-title">Evidence first, interpretation second.</h2>
          <p class="panel-intro">CliniFact keeps source material visible so that retrieved research and model output remain distinct.</p>
          <ol class="workflow-list">
            <li><span>01</span><div><h3>Submit your claim</h3><p>Describe a biomedical or clinical statement you want to explore.</p></div></li>
            <li><span>02</span><div><h3>Retrieve research evidence</h3><p>Search PubMed and ClinicalTrials.gov for relevant records.</p></div></li>
            <li><span>03</span><div><h3>Review the classification</h3><p>The existing BioBERT service produces a research classification label.</p></div></li>
          </ol>
        </aside>
      </section>

      @if (verificationResponse(); as response) {
        <section class="results-dashboard page-container" aria-labelledby="results-title">
          <div class="results-heading">
            <div>
              <p class="eyebrow">Verification results</p>
              <h2 id="results-title">Research context for your claim</h2>
            </div>
            <button class="clear-button" type="button" (click)="clearForm()">Start a new verification</button>
          </div>

          <article class="summary-card">
            <div class="claim-summary">
              <span class="summary-label">Submitted claim</span>
              <p>{{ response.claim }}</p>
            </div>
            <div class="summary-grid">
              <div class="summary-value">
                <span class="summary-label">Verification status</span>
                <strong class="status-value" [class.status-inconclusive]="response.status === 'inconclusive'">{{ formatStatus(response.status) }}</strong>
              </div>
              <div class="summary-value">
                <span class="summary-label">Model prediction</span>
                @if (response.prediction; as prediction) {
                  <strong>{{ formatPredictionLabel(prediction.label) }}</strong>
                  @if (prediction.label_id !== null && prediction.label_id !== undefined) {
                    <small>Label ID {{ prediction.label_id }}</small>
                  }
                } @else {
                  <strong class="muted-value">No prediction</strong>
                  <small>No model output was returned.</small>
                }
              </div>
              <div class="summary-value">
                <span class="summary-label">Model score</span>
                @if (response.prediction?.model_score !== null && response.prediction?.model_score !== undefined) {
                  <strong>{{ formatScore(response.prediction?.model_score ?? 0) }}</strong>
                  <small>Experimental model score</small>
                } @else {
                  <strong class="muted-value">Not available</strong>
                  <small>No score was returned.</small>
                }
              </div>
            </div>
          </article>

          @if (response.prediction?.probabilities; as probabilities) {
            <article class="probability-card">
              <div class="section-title">
                <div><p class="eyebrow">Class probabilities</p><h3>Model output distribution</h3></div>
                <span class="experimental-tag">Experimental</span>
              </div>
              <div class="probability-list">
                @for (label of predictionLabels; track label) {
                  @if (probabilities[label] !== null && probabilities[label] !== undefined) {
                    <div class="probability-row">
                      <div class="probability-label"><span>{{ formatPredictionLabel(label) }}</span><strong>{{ formatScore(probabilities[label]) }}</strong></div>
                      <div class="probability-track"><span [style.width.%]="probabilities[label] * 100"></span></div>
                    </div>
                  }
                }
              </div>
              <p class="score-note">These are model probabilities, not calibrated medical confidence or evidence that a claim is medically true or false.</p>
            </article>
          }

          <section class="evidence-section" aria-labelledby="evidence-title">
            <div class="section-title evidence-title">
              <div><p class="eyebrow">Retrieved evidence</p><h3 id="evidence-title">Research sources in view</h3></div>
              <div class="evidence-counts"><span>{{ response.evidence.length }} total</span><span>{{ pubmedEvidence.length }} PubMed</span><span>{{ clinicalTrialsEvidence.length }} trials</span></div>
            </div>

            @if (response.evidence.length === 0) {
              <div class="empty-evidence"><span class="empty-icon" aria-hidden="true">⌁</span><h4>No evidence was retrieved</h4><p>The API did not return research records for this claim. No model prediction was produced from an empty evidence context.</p></div>
            } @else {
              <div class="evidence-groups">
                <div class="evidence-group">
                  <div class="group-heading"><span class="source-mark pubmed-mark" aria-hidden="true">P</span><h4>PubMed Articles <span>{{ pubmedEvidence.length }}</span></h4></div>
                  @if (pubmedEvidence.length === 0) {
                    <p class="group-empty">No PubMed articles were returned.</p>
                  } @else {
                    @for (item of pubmedEvidence; track item.pmid || item.title) {
                      <article class="evidence-card pubmed-card">
                        <div class="evidence-card-top"><span class="source-label">PubMed article</span>@if (item.publication_date) { <time>{{ item.publication_date }}</time> }</div>
                        <h5>{{ item.title }}</h5>
                        @if (item.abstract_or_excerpt) { <p>{{ item.abstract_or_excerpt }}</p> }
                        <div class="evidence-meta">
                          @if (item.pmid) { <span>PMID <strong>{{ item.pmid }}</strong></span> }
                          @if (item.source_url) { <a [href]="item.source_url" target="_blank" rel="noopener noreferrer">Open PubMed record <span aria-hidden="true">↗</span></a> }
                        </div>
                      </article>
                    }
                  }
                </div>
                <div class="evidence-group">
                  <div class="group-heading"><span class="source-mark trials-mark" aria-hidden="true">T</span><h4>ClinicalTrials.gov Studies <span>{{ clinicalTrialsEvidence.length }}</span></h4></div>
                  @if (clinicalTrialsEvidence.length === 0) {
                    <p class="group-empty">No ClinicalTrials.gov studies were returned.</p>
                  } @else {
                    @for (item of clinicalTrialsEvidence; track item.nct_id || item.title) {
                      <article class="evidence-card trials-card">
                        <div class="evidence-card-top"><span class="source-label">Clinical trial</span>@if (item.study_status) { <span>{{ item.study_status }}</span> }</div>
                        <h5>{{ item.title }}</h5>
                        @if (item.abstract_or_excerpt) { <p>{{ item.abstract_or_excerpt }}</p> }
                        <div class="trial-dates">
                          @if (item.nct_id) { <span>NCT <strong>{{ item.nct_id }}</strong></span> }
                          @if (item.start_date) { <span>Started {{ item.start_date }}</span> }
                          @if (item.completion_date) { <span>Completion {{ item.completion_date }}</span> }
                        </div>
                        @if (item.source_url) { <div class="evidence-meta"><a [href]="item.source_url" target="_blank" rel="noopener noreferrer">Open study record <span aria-hidden="true">↗</span></a></div> }
                      </article>
                    }
                  }
                </div>
              </div>
            }
          </section>

          @if (response.warnings.length > 0 || response.limitations.length > 0) {
            <section class="notes-section" aria-labelledby="notes-title">
              <p class="eyebrow">Interpretation notes</p><h3 id="notes-title">Warnings and limitations</h3>
              <div class="notes-grid">
                @if (response.warnings.length > 0) { <div class="note-box warning-box"><h4>Warnings</h4><ul>@for (warning of response.warnings; track warning) { <li>{{ warning }}</li> }</ul></div> }
                @if (response.limitations.length > 0) { <div class="note-box limitation-box"><h4>Limitations</h4><ul>@for (limitation of response.limitations; track limitation) { <li>{{ limitation }}</li> }</ul></div> }
              </div>
              <p class="research-reminder">CliniFact is an experimental research prototype, not a medical diagnosis or clinical decision-support system. Retrieved articles are not automatically evidence supporting or contradicting a claim.</p>
            </section>
          }
        </section>
      }

      <section class="disclaimer page-container" aria-labelledby="research-notice-title">
        <div class="notice-icon" aria-hidden="true">i</div>
        <div>
          <p class="eyebrow">Research prototype notice</p>
          <h2 id="research-notice-title">Use results as research context.</h2>
          <p>CliniFact is an experimental research prototype. Predictions are not medical diagnoses. Retrieved articles are not automatically evidence supporting or contradicting a claim, and model scores are not calibrated medical confidence.</p>
        </div>
      </section>
    </main>
  `,
  styles: `
    :host { display: block; }
    .page-container { margin: 0 auto; max-width: 80rem; padding-left: var(--page-gutter); padding-right: var(--page-gutter); }
    .verification-page { padding-bottom: clamp(4rem, 8vw, 7rem); }
    .page-intro { padding-bottom: var(--space-8); padding-top: clamp(3.5rem, 7vw, 6rem); }
    .eyebrow { color: var(--color-teal); font-size: .72rem; font-weight: 800; letter-spacing: .13em; margin: 0; text-transform: uppercase; }
    h1, h2, h3 { color: var(--color-navy); font-family: var(--font-display); }
    .page-intro h1 { font-size: clamp(2.5rem, 5vw, 4.5rem); letter-spacing: -.07em; line-height: 1; margin: var(--space-4) 0; }
    .page-intro > p:last-child { color: var(--color-muted); font-size: 1.05rem; line-height: 1.7; margin: 0; max-width: 44rem; }
    .workspace { align-items: start; display: grid; gap: var(--space-6); grid-template-columns: minmax(0, 1.45fr) minmax(18rem, .75fr); }
    .claim-card, .info-panel { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); box-shadow: var(--shadow-card); }
    .claim-card { padding: clamp(1.25rem, 4vw, 2.5rem); }
    .card-heading { align-items: flex-start; display: flex; justify-content: space-between; margin-bottom: var(--space-8); }
    .card-heading h2, .info-panel h2, .disclaimer h2 { font-size: clamp(1.35rem, 2.2vw, 2rem); letter-spacing: -.045em; margin: var(--space-3) 0 0; }
    .step-badge { background: var(--color-blue-soft); border-radius: 99px; color: var(--color-blue); font-size: .7rem; font-weight: 800; padding: .5rem .7rem; }
    .step-badge span { color: var(--color-muted); font-weight: 600; }
    .field-group label { color: var(--color-navy); display: block; font-size: .87rem; font-weight: 750; margin-bottom: var(--space-3); }
    textarea, select { background: #fbfdff; border: 1px solid #c9d8e4; border-radius: var(--radius-md); color: var(--color-ink); outline: none; transition: border-color 160ms ease, box-shadow 160ms ease; width: 100%; }
    textarea { min-height: 12rem; padding: var(--space-4); resize: vertical; }
    select { cursor: pointer; padding: .8rem .9rem; }
    textarea:focus, select:focus { border-color: var(--color-blue); box-shadow: 0 0 0 3px rgb(29 93 155 / 14%); }
    textarea[aria-invalid="true"], select[aria-invalid="true"] { border-color: #b94a48; }
    .field-meta { color: var(--color-muted); display: flex; font-size: .73rem; justify-content: space-between; line-height: 1.45; margin-top: var(--space-2); }
    .limit-near { color: #a25b18; font-weight: 700; }
    .field-error { color: #a53634; font-size: .77rem; line-height: 1.4; margin: var(--space-2) 0 0; }
    .field-hint { color: var(--color-muted); font-size: .74rem; margin: var(--space-2) 0 0; }
    .form-controls { align-items: end; display: flex; gap: var(--space-6); justify-content: space-between; margin-top: var(--space-6); }
    .evidence-field { max-width: 18rem; width: 100%; }
    .form-actions { align-items: center; display: flex; gap: var(--space-3); }
    .primary-button, .clear-button { border-radius: var(--radius-md); cursor: pointer; font-weight: 700; padding: .85rem 1.1rem; }
    .primary-button { align-items: center; background: var(--color-navy); border: 1px solid var(--color-navy); color: var(--color-white); display: inline-flex; gap: .5rem; justify-content: center; min-width: 9.5rem; }
    .primary-button:hover:not(:disabled) { background: var(--color-blue); border-color: var(--color-blue); transform: translateY(-2px); }
    .primary-button:disabled { cursor: not-allowed; opacity: .48; }
    .clear-button { background: transparent; border: 1px solid var(--color-border); color: var(--color-muted); }
    .clear-button:hover { background: var(--color-blue-soft); color: var(--color-navy); }
    .form-status { border-top: 1px solid var(--color-border); color: var(--color-muted); font-size: .75rem; line-height: 1.5; margin: var(--space-6) 0 0; padding-top: var(--space-4); }
    .loading-status { align-items: center; display: flex; gap: .55rem; }
    .status-dot, .spinner { animation: status-pulse 1.2s ease-in-out infinite; background: var(--color-teal); border-radius: 50%; display: inline-block; height: .55rem; width: .55rem; }
    .spinner { animation: spin .8s linear infinite; border: 2px solid rgb(255 255 255 / 35%); border-radius: 50%; border-top-color: currentColor; height: .9rem; width: .9rem; }
    .error-status { color: #a53634; }
    .success-status { color: var(--color-teal); }
    .results-dashboard { padding-top: clamp(3rem, 6vw, 5rem); }
    .results-heading, .section-title, .evidence-title { align-items: flex-start; display: flex; justify-content: space-between; gap: var(--space-4); }
    .results-heading { align-items: center; margin-bottom: var(--space-5); }
    .results-heading h2 { color: var(--color-navy); font-size: clamp(1.7rem, 3vw, 2.5rem); letter-spacing: -.06em; margin: var(--space-3) 0 0; }
    .summary-card, .probability-card, .evidence-section, .notes-section { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); box-shadow: var(--shadow-card); padding: clamp(1.25rem, 4vw, 2rem); }
    .claim-summary { border-bottom: 1px solid var(--color-border); padding-bottom: var(--space-5); }
    .summary-label { color: var(--color-muted); display: block; font-size: .7rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
    .claim-summary p { color: var(--color-navy); font-size: 1.05rem; line-height: 1.55; margin: var(--space-3) 0 0; }
    .summary-grid { display: grid; gap: var(--space-5); grid-template-columns: repeat(3, 1fr); padding-top: var(--space-5); }
    .summary-value strong { color: var(--color-navy); display: block; font-family: var(--font-display); font-size: 1.12rem; margin-top: .5rem; }
    .summary-value small { color: var(--color-muted); display: block; font-size: .73rem; margin-top: .35rem; }
    .status-value { color: var(--color-teal) !important; }
    .status-inconclusive { color: #a25b18 !important; }
    .muted-value { color: var(--color-muted) !important; font-size: .95rem !important; }
    .probability-card { margin-top: var(--space-5); }
    .section-title h3, .notes-section h3 { color: var(--color-navy); font-family: var(--font-display); font-size: 1.35rem; letter-spacing: -.04em; margin: var(--space-2) 0 0; }
    .experimental-tag { background: #fff2df; border-radius: 99px; color: #9a641e; font-size: .68rem; font-weight: 800; padding: .45rem .65rem; }
    .probability-list { margin-top: var(--space-6); max-width: 46rem; }
    .probability-row + .probability-row { margin-top: var(--space-4); }
    .probability-label { color: var(--color-ink); display: flex; font-size: .82rem; justify-content: space-between; margin-bottom: .4rem; }
    .probability-label strong { color: var(--color-navy); }
    .probability-track { background: var(--color-blue-soft); border-radius: 99px; height: .55rem; overflow: hidden; }
    .probability-track span { background: var(--color-blue); border-radius: inherit; display: block; height: 100%; }
    .score-note, .research-reminder { color: var(--color-muted); font-size: .75rem; line-height: 1.55; margin: var(--space-5) 0 0; }
    .evidence-section { margin-top: var(--space-5); }
    .evidence-counts { align-items: center; color: var(--color-muted); display: flex; flex-wrap: wrap; font-size: .72rem; gap: var(--space-3); }
    .evidence-counts span { background: var(--color-page); border-radius: 99px; padding: .45rem .65rem; }
    .evidence-groups { display: grid; gap: var(--space-5); grid-template-columns: repeat(2, 1fr); margin-top: var(--space-6); }
    .group-heading { align-items: center; display: flex; gap: .65rem; }
    .group-heading h4 { color: var(--color-navy); font-family: var(--font-display); margin: 0; }
    .group-heading h4 span { color: var(--color-muted); font-size: .75rem; font-weight: 500; margin-left: .35rem; }
    .source-mark { align-items: center; border-radius: .55rem; display: inline-flex; font-size: .75rem; font-weight: 900; height: 2rem; justify-content: center; width: 2rem; }
    .pubmed-mark { background: var(--color-blue-soft); color: var(--color-blue); }
    .trials-mark { background: #e4f5f3; color: var(--color-teal); }
    .evidence-card { border: 1px solid var(--color-border); border-left: 3px solid var(--color-blue); border-radius: var(--radius-md); margin-top: var(--space-3); padding: var(--space-4); }
    .trials-card { border-left-color: var(--color-teal); }
    .evidence-card-top { align-items: center; color: var(--color-muted); display: flex; font-size: .7rem; justify-content: space-between; gap: var(--space-3); }
    .source-label { color: var(--color-blue); font-size: .68rem; font-weight: 800; text-transform: uppercase; }
    .trials-card .source-label { color: var(--color-teal); }
    .evidence-card h5 { color: var(--color-navy); font-family: var(--font-display); font-size: .98rem; line-height: 1.35; margin: .65rem 0; }
    .evidence-card p { color: var(--color-muted); font-size: .78rem; line-height: 1.6; margin: 0; }
    .evidence-meta, .trial-dates { align-items: center; display: flex; flex-wrap: wrap; font-size: .7rem; gap: var(--space-3); margin-top: var(--space-4); }
    .evidence-meta { justify-content: space-between; }
    .evidence-meta span, .trial-dates span { color: var(--color-muted); }
    .evidence-meta strong, .trial-dates strong { color: var(--color-navy); }
    .evidence-meta a { color: var(--color-blue); font-weight: 750; text-decoration: none; }
    .evidence-meta a:hover { text-decoration: underline; }
    .group-empty { color: var(--color-muted); font-size: .8rem; margin: var(--space-5) 0; }
    .empty-evidence { background: var(--color-page); border-radius: var(--radius-md); margin-top: var(--space-6); padding: var(--space-8); text-align: center; }
    .empty-icon { color: var(--color-blue); font-size: 2rem; }
    .empty-evidence h4 { color: var(--color-navy); font-family: var(--font-display); margin: var(--space-3) 0; }
    .empty-evidence p { color: var(--color-muted); font-size: .82rem; line-height: 1.6; margin: auto; max-width: 34rem; }
    .notes-section { margin-top: var(--space-5); }
    .notes-grid { display: grid; gap: var(--space-4); grid-template-columns: repeat(2, 1fr); margin-top: var(--space-5); }
    .note-box { border-radius: var(--radius-md); padding: var(--space-4); }
    .warning-box { background: #fff7eb; border: 1px solid #f0d7aa; }
    .limitation-box { background: #eef5fa; border: 1px solid #d5e4ee; }
    .note-box h4 { color: var(--color-navy); font-size: .85rem; margin: 0; }
    .note-box ul { color: var(--color-muted); font-size: .78rem; line-height: 1.55; margin: var(--space-3) 0 0; padding-left: 1.1rem; }
    .research-reminder { border-top: 1px solid var(--color-border); padding-top: var(--space-4); }
    .info-panel { background: var(--color-navy); color: #c8d8e6; padding: clamp(1.25rem, 4vw, 2rem); }
    .info-panel h2 { color: var(--color-white); line-height: 1.1; }
    .panel-topline { align-items: center; color: #9ed5d4; display: flex; font-size: .72rem; font-weight: 750; gap: .5rem; letter-spacing: .08em; text-transform: uppercase; }
    .pulse-dot { background: #76cfc9; border-radius: 50%; box-shadow: 0 0 0 5px rgb(118 207 201 / 15%); height: .45rem; width: .45rem; }
    .panel-intro { font-size: .86rem; line-height: 1.6; margin: var(--space-4) 0 0; }
    .workflow-list { list-style: none; margin: var(--space-8) 0 0; padding: 0; }
    .workflow-list li { border-top: 1px solid rgb(255 255 255 / 15%); display: flex; gap: var(--space-3); padding: var(--space-4) 0; }
    .workflow-list li > span { color: #78c8d1; font-size: .7rem; font-weight: 800; padding-top: .15rem; }
    .workflow-list h3 { color: var(--color-white); font-size: .9rem; margin: 0 0 .35rem; }
    .workflow-list p { font-size: .78rem; line-height: 1.5; margin: 0; }
    .disclaimer { align-items: flex-start; background: #eaf3f8; border: 1px solid #cfe2ee; border-radius: var(--radius-lg); display: flex; gap: var(--space-4); margin-top: var(--space-6); padding: clamp(1.25rem, 4vw, 2rem); }
    .notice-icon { align-items: center; background: var(--color-blue); border-radius: 50%; color: var(--color-white); display: flex; flex: 0 0 2rem; font-weight: 800; height: 2rem; justify-content: center; }
    .disclaimer h2 { margin-bottom: var(--space-3); }
    .disclaimer p:last-child { color: var(--color-ink); font-size: .86rem; line-height: 1.65; margin: 0; max-width: 65rem; }
    @media (max-width: 800px) { .workspace { grid-template-columns: 1fr; } .info-panel { order: -1; } .evidence-groups, .notes-grid { grid-template-columns: 1fr; } }
    @media (max-width: 560px) { .form-controls { align-items: stretch; flex-direction: column; } .evidence-field { max-width: none; } .form-actions { justify-content: flex-end; } .disclaimer { flex-direction: column; } .results-heading, .evidence-title { align-items: flex-start; flex-direction: column; } .summary-grid { grid-template-columns: 1fr; } }
    @keyframes spin { to { transform: rotate(360deg); } }
    @keyframes status-pulse { 50% { opacity: .45; } }
    @media (prefers-reduced-motion: reduce) { textarea, select, .primary-button, .status-dot, .spinner { animation: none; transition: none; } }
  `,
})
export class VerificationComponent {
  private readonly formBuilder = inject(FormBuilder);
  private readonly apiService = inject(ClinifactApiService);

  protected readonly claimMaxLength = CLAIM_MAX_LENGTH;
  protected readonly minEvidenceItems = MIN_EVIDENCE_ITEMS;
  protected readonly maxEvidenceItems = MAX_EVIDENCE_ITEMS;
  protected readonly predictionLabels: PredictionLabel[] = ['inconclusive', 'evidence', 'NEI'];
  protected readonly evidenceOptions = Array.from(
    { length: MAX_EVIDENCE_ITEMS },
    (_, index) => index + 1,
  );
  protected readonly verificationForm = this.formBuilder.nonNullable.group({
    claim: this.formBuilder.nonNullable.control('', {
      validators: [Validators.required, Validators.maxLength(CLAIM_MAX_LENGTH), nonWhitespaceValidator],
    }),
    maxEvidenceItems: this.formBuilder.nonNullable.control(DEFAULT_EVIDENCE_ITEMS, {
      validators: [
        Validators.min(MIN_EVIDENCE_ITEMS),
        Validators.max(MAX_EVIDENCE_ITEMS),
      ],
    }),
  });
  protected readonly isLoading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly verificationResponse = signal<VerificationResponse | null>(null);

  protected get claimControl() {
    return this.verificationForm.controls.claim;
  }

  protected get claimLength(): number {
    return this.claimControl.value.length;
  }

  protected get claimInvalid(): boolean {
    return this.claimControl.invalid && (this.claimControl.touched || this.claimControl.dirty);
  }

  protected get evidenceInvalid(): boolean {
    const value = this.verificationForm.controls.maxEvidenceItems.value;
    return value < MIN_EVIDENCE_ITEMS || value > MAX_EVIDENCE_ITEMS;
  }

  protected get pubmedEvidence(): EvidenceItem[] {
    return this.verificationResponse()?.evidence.filter((item) => item.source === 'PubMed') ?? [];
  }

  protected get clinicalTrialsEvidence(): EvidenceItem[] {
    return (
      this.verificationResponse()?.evidence.filter(
        (item) => item.source === 'ClinicalTrials.gov',
      ) ?? []
    );
  }

  protected formatStatus(status: VerificationResponse['status']): string {
    return status.replace('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  protected formatPredictionLabel(label: PredictionLabel): string {
    if (label === 'NEI') {
      return 'NEI';
    }
    return label.charAt(0).toUpperCase() + label.slice(1);
  }

  protected formatScore(score: number): string {
    return `${(score * 100).toFixed(1)}%`;
  }

  protected submitClaim(): void {
    if (this.verificationForm.invalid || this.isLoading()) {
      if (this.verificationForm.invalid) {
        this.verificationForm.markAllAsTouched();
      }
      return;
    }

    this.errorMessage.set(null);
    this.verificationResponse.set(null);
    this.isLoading.set(true);
    const request = {
      claim: this.claimControl.value.trim(),
      max_evidence_items: this.verificationForm.controls.maxEvidenceItems.value,
    };

    this.apiService.verifyClaim(request).subscribe({
      next: (response) => {
        this.verificationResponse.set(response);
        this.isLoading.set(false);
      },
      error: (error: unknown) => {
        this.errorMessage.set(this.getErrorMessage(error));
        this.isLoading.set(false);
      },
    });
  }

  private getErrorMessage(error: unknown): string {
    if (!(error instanceof HttpErrorResponse)) {
      return error instanceof Error
        ? error.message
        : 'The verification service returned an unexpected response. Please try again.';
    }

    if (error.status === 0) {
      return 'The CliniFact API is unavailable. Check that the backend is running and try again.';
    }
    if (error.status === 422) {
      return 'The claim could not be accepted. Check the claim and evidence limit, then try again.';
    }
    if (error.status === 503) {
      return 'The verification service is temporarily unavailable. Please try again shortly.';
    }
    return 'The verification service encountered an error. Please try again.';
  }

  protected clearForm(): void {
    this.verificationForm.reset({
      claim: '',
      maxEvidenceItems: DEFAULT_EVIDENCE_ITEMS,
    });
    this.errorMessage.set(null);
    this.verificationResponse.set(null);
  }
}
