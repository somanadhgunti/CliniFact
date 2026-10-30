import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';
import { routes } from './app.routes';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter(routes)],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should render the CliniFact navigation', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.brand strong')?.textContent).toContain('CliniFact');
    expect(compiled.querySelector('a[href="/verification"]')).toBeTruthy();
  });

  it('should toggle the mobile navigation menu accessibly', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    const toggle = compiled.querySelector('.menu-toggle') as HTMLButtonElement;
    const navigation = compiled.querySelector('#primary-navigation') as HTMLElement;

    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(navigation.classList.contains('is-open')).toBeFalse();

    toggle.click();
    fixture.detectChanges();

    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(navigation.classList.contains('is-open')).toBeTrue();
  });
});
