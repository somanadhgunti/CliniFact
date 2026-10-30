import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', title: 'CliniFact | Clinical evidence verification', loadComponent: () => import('./features/home/home.component').then((module) => module.HomeComponent) },
  { path: 'verification', title: 'Verify a claim | CliniFact', loadComponent: () => import('./features/verification/verification.component').then((module) => module.VerificationComponent) },
  { path: 'about', title: 'About | CliniFact', loadComponent: () => import('./features/about/about.component').then((module) => module.AboutComponent) },
  { path: '**', redirectTo: '' },
];
