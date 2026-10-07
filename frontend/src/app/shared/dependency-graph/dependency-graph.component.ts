import {
  Component,
  input,
  computed,
  signal,
  inject,
  ChangeDetectionStrategy,
} from "@angular/core";
import { Commitment } from "../../core/models";
import { Panels } from "../../core/panels.service";
@Component({
  selector: "dependency-graph",
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./dependency-graph.component.html",
  styleUrl: "./dependency-graph.component.scss",
})
export class DependencyGraph {
  Math = Math;
  items = input<Commitment[]>([]);
  focus = input("");
  zoom = signal(1);
  panels = inject(Panels);
  layout = computed(() => {
    const all = this.items();
    const map = new Map(all.map((c) => [c.id, c]));
    const indegree = new Map(
      all.map((c) => [c.id, c.dependencies.filter((d) => map.has(d)).length]),
    );
    const outgoing = new Map<string, string[]>();
    for (const c of all)
      for (const d of c.dependencies)
        if (map.has(d)) outgoing.set(d, [...(outgoing.get(d) || []), c.id]);
    const levels = new Map<string, number>();
    const queue = all.filter((c) => indegree.get(c.id) === 0).map((c) => c.id);
    let cursor = 0;
    while (cursor < queue.length) {
      const id = queue[cursor++];
      const level = levels.get(id) || 0;
      levels.set(id, level);
      for (const next of outgoing.get(id) || []) {
        levels.set(next, Math.max(levels.get(next) || 0, level + 1));
        indegree.set(next, indegree.get(next)! - 1);
        if (indegree.get(next) === 0) queue.push(next);
      }
    }
    for (const c of all) if (!levels.has(c.id)) levels.set(c.id, 0);
    const counts = new Map<number, number>();
    const nodes = [...all]
      .sort(
        (a, b) =>
          levels.get(a.id)! - levels.get(b.id)! ||
          a.owner.localeCompare(b.owner) ||
          a.title.localeCompare(b.title),
      )
      .map((c) => {
        const l = levels.get(c.id)!;
        const i = counts.get(l) || 0;
        counts.set(l, i + 1);
        return { ...c, x: 24 + i * 275, y: 24 + l * 175 };
      });
    const positions = new Map(nodes.map((n) => [n.id, n]));
    const edges = nodes.flatMap((c) =>
      c.dependencies.flatMap((id) => {
        const pre = positions.get(id);
        return pre
          ? [
              {
                key: id + c.id,
                path: `M ${pre.x + 120} ${pre.y + 110} C ${pre.x + 120} ${pre.y + 145}, ${c.x + 120} ${c.y - 35}, ${c.x + 120} ${c.y}`,
              },
            ]
          : [];
      }),
    );
    return {
      nodes,
      edges,
      width: Math.max(300, ...nodes.map((n) => n.x + 265)),
      height: Math.max(160, ...nodes.map((n) => n.y + 135)),
    };
  });
}
