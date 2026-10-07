import {
  Component,
  inject,
  signal,
  OnInit,
  ChangeDetectionStrategy,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Api } from '../core/api';
import { User } from '../core/models';

interface ProfileData {
  user: User;
  manager: User | null;
  members: User[];
  available: User[];
}

@Component({
  standalone: true,
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="eyebrow">YOUR ACCOUNT</div>
    <h1>My profile</h1>

    @if (data(); as d) {
      <section>
        <div class="section-heading">
          <div>
            <h2>{{ d.user.name }}</h2>
            <p class="muted">
              {{ d.user.role }} · {{ d.user.team }}
            </p>
          </div>

          @if (d.user.is_manager) {
            <span class="badge">Manager</span>
          }
        </div>

        <form (ngSubmit)="save()">
          <label>
            Name
            <input
              name="name"
              [(ngModel)]="name"
              required
              maxlength="120"
              [disabled]="working()"
            />
          </label>

          <p class="muted">
            Username: {{ name.trim().toLowerCase() }}
            — changing your name changes your login username.
          </p>

          <label>
            Email
            <input
              name="email"
              type="email"
              [(ngModel)]="email"
              required
              maxlength="200"
              [disabled]="working()"
            />
          </label>

          <button
            type="submit"
            class="primary"
            [disabled]="
              working() || !name.trim() || !email.trim()
            "
          >
            {{ working() ? 'Please wait…' : 'Save profile' }}
          </button>
        </form>

        @if (message()) {
          <p role="status">{{ message() }}</p>
        }
      </section>

      <section>
        <h2>My manager</h2>

        @if (d.manager; as manager) {
          <strong>{{ manager.name }}</strong>
          <p class="muted">
            {{ manager.role }} · {{ manager.team }}
          </p>
        } @else {
          <p class="muted">None</p>
        }
      </section>

      @if (d.user.is_manager) {
        <section>
          <div class="section-heading">
            <h2>People in my team</h2>
            <span class="badge">
              {{ d.members.length }} people
            </span>
          </div>

          <div class="people-grid">
            @for (member of d.members; track member.id) {
              <article class="person-card">
                <strong>{{ member.name }}</strong>
                <p class="muted">
                  {{ member.role }} · {{ member.team }}
                </p>

                <button
                  type="button"
                  [disabled]="working()"
                  (click)="remove(member)"
                >
                  Remove from team
                </button>
              </article>
            } @empty {
              <p class="empty">No team members yet.</p>
            }
          </div>
        </section>

        <section>
          <h2>Add a team member</h2>
          <p class="muted">
            Only people without a manager can be added.
          </p>

          <div class="toolbar">
            <select
              aria-label="Available team member"
              [ngModel]="selectedUser"
              (ngModelChange)="selectedUser = $event"
              [disabled]="working()"
            >
              <option value="">Choose a person</option>

              @for (user of d.available; track user.id) {
                <option [value]="user.id">
                  {{ user.name }} · {{ user.role }}
                </option>
              }
            </select>

            <button
              type="button"
              class="primary"
              [disabled]="working() || !selectedUser"
              (click)="add()"
            >
              Add to team
            </button>
          </div>

          @if (!d.available.length) {
            <p class="muted">
              No eligible users are available.
            </p>
          }
        </section>
      }
    } @else {
      <p class="empty">Loading profile…</p>
    }
  `,
})
export class Profile implements OnInit {
  api = inject(Api);

  data = signal<ProfileData | null>(null);
  working = signal(false);
  message = signal('');

  name = '';
  email = '';
  selectedUser = '';

  async ngOnInit(): Promise<void> {
    try {
      const result = await this.api.call<ProfileData>(
        'GET',
        '/profile',
      );
      this.apply(result);
    } catch {
      // Api.call already exposes the error.
    }
  }

  private apply(result: ProfileData): void {
    this.data.set(result);
    this.api.user.set(result.user);
    this.name = result.user.name;
    this.email = result.user.email;
    this.selectedUser = '';
  }

  private async mutate(
    method: string,
    path: string,
    body?: unknown,
    success = 'Saved.',
  ): Promise<void> {
    if (this.working()) return;

    this.working.set(true);
    this.message.set('');

    try {
      const result = await this.api.call<ProfileData>(
        method,
        path,
        body,
      );

      this.apply(result);
      this.api.changed();
      this.message.set(success);

      try {
        await this.api.loadUsers();
      } catch {
        this.api.error.set(
          'Changes saved, but the user directory could not refresh.',
        );
      }
    } catch {
      // Keep the current page and display the backend error.
    } finally {
      this.working.set(false);
    }
  }

  async save(): Promise<void> {
    await this.mutate(
      'PATCH',
      '/profile',
      {
        name: this.name.trim(),
        email: this.email.trim(),
      },
      'Profile updated.',
    );
  }

  async add(): Promise<void> {
    if (!this.selectedUser) return;

    await this.mutate(
      'POST',
      '/profile/team/' + encodeURIComponent(this.selectedUser),
      undefined,
      'Team member added.',
    );
  }

  async remove(member: User): Promise<void> {
    if (!window.confirm(
      'Remove ' + member.name + ' from your team?',
    )) return;

    await this.mutate(
      'DELETE',
      '/profile/team/' + encodeURIComponent(member.id),
      undefined,
      'Team member removed.',
    );
  }
}