import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { VerificationResponse } from '../../models/verification.models';
import { VerificationComponent } from './verification.component';

describe('VerificationComponent', () => {
  let component: VerificationComponent;
  let fixture: ComponentFixture<VerificationComponent>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [VerificationComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    fixture = TestBed.createComponent(VerificationComponent);
    component = fixture.componentInstance;
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  it('starts with an invalid empty claim and the default evidence count', () => {
    expect(component['verificationForm'].invalid).toBeTrue();
    expect(component['verificationForm'].controls.maxEvidenceItems.value).toBe(5);
    expect(fixture.nativeElement.querySelector('.primary-button').disabled).toBeTrue();
  });

  it('rejects whitespace-only claims', () => {
    const claim = component['verificationForm'].controls.claim;
    claim.setValue('   ');
    claim.markAsTouched();
    fixture.detectChanges();

    expect(claim.hasError('whitespace')).toBeTrue();
    expect(fixture.nativeElement.querySelector('.field-error')?.textContent).toContain(
      'Enter a clinical claim',
    );
  });

  it('enforces the 4,000 character claim limit and updates the counter', () => {
    const claim = component['verificationForm'].controls.claim;
    claim.setValue('a'.repeat(4000));
    fixture.detectChanges();

    expect(claim.valid).toBeTrue();
    expect(fixture.nativeElement.querySelector('.field-meta')?.textContent).toContain('4000 / 4000');

    claim.setValue('a'.repeat(4001));
    expect(claim.hasError('maxlength')).toBeTrue();
  });

  it('enforces the evidence result range', () => {
    const evidence = component['verificationForm'].controls.maxEvidenceItems;
    evidence.setValue(0);
    expect(evidence.hasError('min')).toBeTrue();

    evidence.setValue(21);
    expect(evidence.hasError('max')).toBeTrue();
  });

  it('resets the claim and evidence count', () => {
    component['verificationForm'].setValue({
      claim: 'A clinical research claim.',
      maxEvidenceItems: 12,
    });

    component['clearForm']();

    expect(component['verificationForm'].value).toEqual({
      claim: '',
      maxEvidenceItems: 5,
    });
  });

  it('submits the valid claim with the backend request shape and stores the response', () => {
    component['verificationForm'].setValue({
      claim: 'A clinical research claim.',
      maxEvidenceItems: 7,
    });

    component['submitClaim']();
    fixture.detectChanges();
    expect(component['isLoading']()).toBeTrue();
    expect(fixture.nativeElement.querySelector('.loading-status')?.textContent).toContain(
      'Retrieving research evidence',
    );

    const request = http.expectOne('http://localhost:8000/api/verify');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      claim: 'A clinical research claim.',
      max_evidence_items: 7,
    });

    request.flush({
      claim: 'A clinical research claim.',
      prediction: null,
      evidence: [],
      status: 'inconclusive',
      warnings: ['No evidence was retrieved; no model prediction was produced.'],
      limitations: ['Search results are not proof that a claim is supported or contradicted.'],
    });
    fixture.detectChanges();

    expect(component['isLoading']()).toBeFalse();
    expect(component['verificationResponse']()?.status).toBe('inconclusive');
    expect(fixture.nativeElement.querySelector('.success-status')?.textContent).toContain(
      'Verification completed',
    );
  });

  it('prevents duplicate submissions while a request is loading', () => {
    component['verificationForm'].controls.claim.setValue('A clinical research claim.');
    component['submitClaim']();
    component['submitClaim']();

    const requests = http.match('http://localhost:8000/api/verify');
    expect(requests.length).toBe(1);
    requests[0].flush({
      claim: 'A clinical research claim.',
      prediction: null,
      evidence: [],
      status: 'inconclusive',
      warnings: [],
      limitations: [],
    });
  });

  it('shows controlled messages for HTTP validation and service failures', () => {
    component['verificationForm'].controls.claim.setValue('A clinical research claim.');
    component['submitClaim']();
    http.expectOne('http://localhost:8000/api/verify').flush(
      { detail: 'invalid request' },
      { status: 422, statusText: 'Unprocessable Entity' },
    );
    expect(component['errorMessage']()).toContain('claim could not be accepted');
    expect(component['verificationForm'].controls.claim.value).toBe('A clinical research claim.');

    component['submitClaim']();
    http.expectOne('http://localhost:8000/api/verify').flush(
      { detail: 'unavailable' },
      { status: 503, statusText: 'Service Unavailable' },
    );
    expect(component['errorMessage']()).toContain('temporarily unavailable');

    component['submitClaim']();
    http.expectOne('http://localhost:8000/api/verify').error(new ProgressEvent('error'));
    expect(component['errorMessage']()).toContain('API is unavailable');
  });

  it('handles malformed success responses without fabricating a result', () => {
    component['verificationForm'].controls.claim.setValue('A clinical research claim.');
    component['submitClaim']();
    http.expectOne('http://localhost:8000/api/verify').flush({ status: 'completed' });

    expect(component['verificationResponse']()).toBeNull();
    expect(component['errorMessage']()).toContain('unexpected response');
    expect(component['isLoading']()).toBeFalse();
  });

  it('does not submit an invalid form', () => {
    component['submitClaim']();
    expect(http.match('http://localhost:8000/api/verify')).toEqual([]);
    expect(component['isLoading']()).toBeFalse();
  });

  it('renders the completed response summary, probabilities, and evidence by source', () => {
    submitResponse({
      claim: 'A clinical research claim.',
      prediction: {
        label: 'evidence',
        label_id: 1,
        model_score: 0.84,
        probabilities: { inconclusive: 0.1, evidence: 0.84, NEI: 0.06 },
      },
      evidence: [
        {
          source: 'PubMed',
          title: 'Exercise and glycemic control',
          abstract_or_excerpt: 'A research abstract.',
          publication_date: '2024-01-02',
          pmid: '12345',
          source_url: 'https://pubmed.ncbi.nlm.nih.gov/12345/',
        },
        {
          source: 'ClinicalTrials.gov',
          title: 'Exercise intervention study',
          abstract_or_excerpt: 'A study summary.',
          nct_id: 'NCT01234567',
          study_status: 'Recruiting',
          start_date: '2024-02-01',
          completion_date: '2025-02-01',
          source_url: 'https://clinicaltrials.gov/study/NCT01234567',
        },
      ],
      status: 'completed',
      warnings: ['A source warning.'],
      limitations: ['A model limitation.'],
    });

    expect(fixture.nativeElement.querySelector('.results-dashboard')).toBeTruthy();
    expect(fixture.nativeElement.querySelector('.summary-card')?.textContent).toContain('Evidence');
    expect(fixture.nativeElement.querySelector('.summary-card')?.textContent).toContain('Label ID 1');
    expect(fixture.nativeElement.querySelector('.probability-card')?.textContent).toContain('84.0%');
    expect(fixture.nativeElement.querySelectorAll('.pubmed-card').length).toBe(1);
    expect(fixture.nativeElement.querySelectorAll('.trials-card').length).toBe(1);
    expect(fixture.nativeElement.querySelector('.pubmed-card')?.textContent).toContain('PMID 12345');
    expect(fixture.nativeElement.querySelector('.trials-card')?.textContent).toContain('NCT01234567');
    expect(fixture.nativeElement.querySelector('.warning-box')?.textContent).toContain('A source warning.');
    expect(fixture.nativeElement.querySelector('.limitation-box')?.textContent).toContain('A model limitation.');
  });

  it('renders every prediction label without treating it as a medical conclusion', () => {
    for (const label of ['inconclusive', 'evidence', 'NEI'] as const) {
      component['verificationResponse'].set({
        claim: 'Claim',
        prediction: { label, label_id: 0 },
        evidence: [],
        status: 'completed',
        warnings: [],
        limitations: [],
      });
      fixture.detectChanges();

      expect(fixture.nativeElement.querySelector('.summary-card')?.textContent).toContain(
        label === 'NEI' ? 'NEI' : label.charAt(0).toUpperCase() + label.slice(1),
      );
    }
  });

  it('renders missing prediction and optional metadata safely', () => {
    submitResponse({
      claim: 'Claim without a model result.',
      prediction: null,
      evidence: [
        { source: 'PubMed', title: 'Title only' },
        { source: 'ClinicalTrials.gov', title: 'Study title only' },
      ],
      status: 'inconclusive',
      warnings: [],
      limitations: [],
    });

    expect(fixture.nativeElement.querySelector('.muted-value')?.textContent).toContain('No prediction');
    expect(fixture.nativeElement.querySelector('.pubmed-card')?.textContent).toContain('Title only');
    expect(fixture.nativeElement.querySelector('.trials-card')?.textContent).toContain('Study title only');
    expect(fixture.nativeElement.querySelector('.probability-card')).toBeNull();
    expect(fixture.nativeElement.querySelectorAll('a[target="_blank"][rel="noopener noreferrer"]').length).toBe(0);
  });

  it('renders the empty evidence state and source counts', () => {
    submitResponse({
      claim: 'Claim with no records.',
      prediction: null,
      evidence: [],
      status: 'inconclusive',
      warnings: ['No evidence was retrieved.'],
      limitations: ['Search relevance is not proof.'],
    });

    expect(fixture.nativeElement.querySelector('.empty-evidence')?.textContent).toContain(
      'No evidence was retrieved',
    );
    expect(fixture.nativeElement.querySelector('.evidence-counts')?.textContent).toContain('0 total');
    expect(fixture.nativeElement.querySelector('.notes-section')).toBeTruthy();
  });

  it('uses safe external links for returned official URLs', () => {
    submitResponse({
      claim: 'Claim',
      prediction: null,
      evidence: [
        {
          source: 'PubMed',
          title: 'Article',
          source_url: 'https://pubmed.ncbi.nlm.nih.gov/1/',
        },
      ],
      status: 'completed',
      warnings: [],
      limitations: [],
    });

    const link = fixture.nativeElement.querySelector('.evidence-card a') as HTMLAnchorElement;
    expect(link.target).toBe('_blank');
    expect(link.rel).toContain('noopener');
    expect(link.rel).toContain('noreferrer');
  });

  it('clears the stored response and starts a new verification', () => {
    submitResponse({
      claim: 'Claim',
      prediction: null,
      evidence: [],
      status: 'inconclusive',
      warnings: [],
      limitations: [],
    });

    component['clearForm']();
    fixture.detectChanges();

    expect(component['verificationResponse']()).toBeNull();
    expect(fixture.nativeElement.querySelector('.results-dashboard')).toBeNull();
    expect(component['verificationForm'].controls.claim.value).toBe('');
  });

  function submitResponse(response: VerificationResponse): void {
    component['verificationForm'].controls.claim.setValue(response.claim);
    component['submitClaim']();
    const request = http.expectOne('http://localhost:8000/api/verify');
    request.flush(response);
    fixture.detectChanges();
  }
});
