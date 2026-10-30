import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { map } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  HealthResponse,
  isVerificationResponse,
  VerificationRequest,
  VerificationResponse,
} from '../../models/verification.models';

@Injectable({ providedIn: 'root' })
export class ClinifactApiService {
  private readonly http = inject(HttpClient);
  private readonly apiBaseUrl = environment.apiBaseUrl.replace(/\/$/, '');

  getHealth(): Observable<HealthResponse> {
    return this.http.get<HealthResponse>(`${this.apiBaseUrl}/api/health`);
  }

  verifyClaim(request: VerificationRequest): Observable<VerificationResponse> {
    return this.http
      .post<unknown>(`${this.apiBaseUrl}/api/verify`, request)
      .pipe(
        map((response) => {
          if (!isVerificationResponse(response)) {
            throw new Error('The verification service returned an unexpected response.');
          }
          return response;
        }),
      );
  }
}
