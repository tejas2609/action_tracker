import {
  ChangeDetectionStrategy,
  Component,
  computed,
  input,
} from "@angular/core";

import { AgendaGraph } from "./agenda.models";

@Component({
  selector: "app-agenda-graph",
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <p>Arrows point from prerequisite to dependent commitment.</p>

    @if (layout().cycle) {
      <p role="alert">
        A dependency cycle exists. Resolve it before planning execution.
      </p>
    }

    <div
      class="graph-scroll"
      tabindex="0"
      aria-label="Scrollable dependency graph"
    >
      <svg
        [attr.width]="layout().width"
        [attr.height]="layout().height"
        role="img"
        aria-label="Commitment dependency graph"
      >
        @for (edge of layout().edges; track edge.key) {
          <path
            [attr.d]="edge.path"
            fill="none"
            stroke="#94a3b8"
            stroke-width="2"
          />

          <polygon
            [attr.points]="edge.arrow"
            fill="#94a3b8"
          />
        }

        @for (node of layout().nodes; track node.task.id) {
          <g
            [attr.transform]="
              'translate(' + node.x + ',' + node.y + ')'
            "
          >
            <title>
              {{ node.task.title }} —
              {{ node.task.owner }} —
              {{ node.task.meeting_title }} —
              {{ node.task.reasons.join("; ") }}
            </title>

            <rect
              width="224"
              height="94"
              rx="10"
              [attr.fill]="
                node.task.status === 'completed'
                  ? '#e5f4eb'
                  : node.task.external
                    ? '#eef2ff'
                    : '#ffffff'
              "
              stroke="#cbd5e1"
            />

            <text x="12" y="23">
              {{ short(node.task.title, 27) }}
            </text>

            <text x="12" y="44" class="meta">
              {{ short(node.task.owner, 27) }}
            </text>

            <text x="12" y="64" class="meta">
              {{ short(node.task.meeting_title, 29) }}
            </text>

            <text x="12" y="83" class="meta">
              {{
                node.task.status === "completed"
                  ? "Completed"
                  : node.task.ready
                    ? "Ready"
                    : "Waiting / blocked"
              }}
            </text>
          </g>
        }
      </svg>
    </div>

    <details>
      <summary>Dependency text view</summary>

      @for (node of graph().nodes; track node.id) {
        <p>
          <strong>{{ node.title }}</strong>
          · {{ node.owner }}
          · {{ node.meeting_title }}
          · {{ node.status }}
        </p>
      }

      @for (
        edge of graph().edges;
        track edge.source + ":" + edge.target
      ) {
        <p>{{ name(edge.source) }} → {{ name(edge.target) }}</p>
      }
    </details>
  `,
  styles: [`
    :host {
      display: block;
    }

    .graph-scroll {
      overflow: auto;
      max-height: 560px;
      border: 1px solid #dce5df;
      border-radius: 12px;
      background: #f8faf9;
    }

    svg {
      display: block;
    }

    text {
      font: 13px system-ui;
      fill: #1e293b;
    }

    .meta {
      font-size: 11px;
      fill: #64748b;
    }

    p {
      color: #64748b;
    }
  `],
})
export class AgendaGraphComponent {
  graph = input.required<AgendaGraph>();

  short(value: string, size: number): string {
    return value.length > size
      ? value.slice(0, size - 1) + "…"
      : value;
  }

  name(id: string): string {
    return this.graph().nodes.find(node => node.id === id)?.title || id;
  }

  layout = computed(() => {
    const graph = this.graph();
    const ids = new Set(graph.nodes.map(node => node.id));

    const incoming = new Map(
      graph.nodes.map(node => [node.id, 0]),
    );

    const children = new Map<string, string[]>();

    const depths = new Map(
      graph.nodes.map(node => [node.id, 0]),
    );

    for (const edge of graph.edges) {
      if (!ids.has(edge.source) || !ids.has(edge.target)) {
        continue;
      }

      incoming.set(
        edge.target,
        incoming.get(edge.target)! + 1,
      );

      children.set(
        edge.source,
        [...(children.get(edge.source) || []), edge.target],
      );
    }

    const queue = graph.nodes
      .filter(node => incoming.get(node.id) === 0)
      .map(node => node.id);

    let cursor = 0;

    while (cursor < queue.length) {
      const id = queue[cursor++];

      for (const child of children.get(id) || []) {
        depths.set(
          child,
          Math.max(
            depths.get(child)!,
            depths.get(id)! + 1,
          ),
        );

        incoming.set(
          child,
          incoming.get(child)! - 1,
        );

        if (!incoming.get(child)) {
          queue.push(child);
        }
      }
    }

    const lanes = new Map<number, number>();

    const nodes = graph.nodes.map(task => {
      const depth = depths.get(task.id)!;
      const lane = lanes.get(depth) || 0;

      lanes.set(depth, lane + 1);

      return {
        task,
        x: 20 + depth * 280,
        y: 20 + lane * 120,
      };
    });

    const positions = new Map(
      nodes.map(node => [node.task.id, node]),
    );

    const edges = graph.edges.flatMap(edge => {
      const source = positions.get(edge.source);
      const target = positions.get(edge.target);

      if (!source || !target) {
        return [];
      }

      const x1 = source.x + 224;
      const y1 = source.y + 47;
      const x2 = target.x;
      const y2 = target.y + 47;
      const middle = (x1 + x2) / 2;

      return [{
        key: edge.source + ":" + edge.target,
        path:
          `M ${x1} ${y1} ` +
          `C ${middle} ${y1}, ${middle} ${y2}, ${x2} ${y2}`,
        arrow:
          `${x2},${y2} ` +
          `${x2 - 8},${y2 - 4} ` +
          `${x2 - 8},${y2 + 4}`,
      }];
    });

    return {
      nodes,
      edges,
      cycle: cursor < graph.nodes.length,
      width: Math.max(
        280,
        ...nodes.map(node => node.x + 244),
      ),
      height: Math.max(
        140,
        ...nodes.map(node => node.y + 114),
      ),
    };
  });
}