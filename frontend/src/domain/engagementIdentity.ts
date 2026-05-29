import type { Engagement } from "../types/domain";
import { taskNameFromConfig } from "./instanceConfig";

export function engagementConfig(engagement: Pick<Engagement, "instance_config">) {
  return engagement.instance_config;
}

export function engagementIdentityLabel(
  engagement: Pick<Engagement, "instance_config" | "name" | "version">,
): string {
  const taskName = taskNameFromConfig(engagementConfig(engagement)) || engagement.name.trim() || "任务";
  return `${taskName} · v${engagement.version}`;
}

export function engagementTechnicalId(engagement: Pick<Engagement, "id">): string {
  return engagement.id;
}

