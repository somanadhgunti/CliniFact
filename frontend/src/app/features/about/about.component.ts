import { Component } from '@angular/core';

@Component({
  selector: 'app-about',
  template: `<section class="placeholder"><p class="eyebrow">About CliniFact</p><h1>Research transparency is part of the interface.</h1><p>CliniFact is being developed as a clinical research application. It keeps retrieved sources, model predictions and limitations distinct.</p></section>`,
  styles: `.placeholder { margin: 0 auto; max-width: 76rem; padding: 6rem var(--page-gutter); } .eyebrow { color: var(--color-teal); font-size: .75rem; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; } h1 { color: var(--color-navy); font-size: clamp(2rem, 5vw, 3.5rem); letter-spacing: -.05em; line-height: 1.05; margin: var(--space-4) 0; max-width: 16ch; } p:last-child { color: var(--color-muted); font-size: 1.1rem; line-height: 1.7; max-width: 38rem; }`,
})
export class AboutComponent {}
