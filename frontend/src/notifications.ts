import { LocalNotifications } from "@capacitor/local-notifications";

import type { NotificationStatus, TenderResult } from "./types";

function notificationId(bidId: string, offsetHours: number): number {
  const digits = bidId.replace(/\D/g, "");
  const base = Number(digits.slice(-6) || "1");
  const suffix = offsetHours === 24 ? 1 : 2;
  return base * 10 + suffix;
}

function scheduleTime(endDate: string, offsetHours: number): Date | null {
  const end = new Date(endDate);
  if (Number.isNaN(end.getTime())) {
    return null;
  }
  const at = new Date(end.getTime() - offsetHours * 60 * 60 * 1000);
  if (at.getTime() <= Date.now()) {
    return null;
  }
  return at;
}

export async function ensureNotificationPermission(): Promise<NotificationStatus> {
  try {
    const current = await LocalNotifications.checkPermissions();
    if (current.display === "granted") {
      return "granted";
    }
    const requested = await LocalNotifications.requestPermissions();
    return requested.display === "granted" ? "granted" : "denied";
  } catch {
    return "denied";
  }
}

export async function syncTenderNotifications(tenders: TenderResult[]): Promise<void> {
  const ids = tenders.flatMap((tender) => [
    { id: notificationId(tender.bidId, 24) },
    { id: notificationId(tender.bidId, 2) },
  ]);

  try {
    if (ids.length) {
      await LocalNotifications.cancel({ notifications: ids });
    }

    const notifications = tenders.flatMap((tender) => {
      return [24, 2]
        .map((offsetHours) => {
          const at = scheduleTime(tender.endDate, offsetHours);
          if (!at) {
            return null;
          }
          return {
            id: notificationId(tender.bidId, offsetHours),
            title: `${tender.bidNumber} closes soon`,
            body: `${tender.category} closes in ${offsetHours} hour${offsetHours === 1 ? "" : "s"}.`,
            schedule: { at },
            extra: { bidId: tender.bidId },
          };
        })
        .filter(Boolean);
    });

    if (notifications.length) {
      await LocalNotifications.schedule({
        notifications: notifications as Array<{
          id: number;
          title: string;
          body: string;
          schedule: { at: Date };
          extra: { bidId: string };
        }>,
      });
    }
  } catch {
    // Ignore plugin errors in plain browser development.
  }
}

export async function registerNotificationTapListener(
  onOpenTender: (bidId: string) => void,
): Promise<() => void> {
  try {
    const handle = await LocalNotifications.addListener(
      "localNotificationActionPerformed",
      (event) => {
        const bidId = String(event.notification.extra?.["bidId"] || "");
        if (bidId) {
          onOpenTender(bidId);
        }
      },
    );
    return () => {
      handle.remove();
    };
  } catch {
    return () => {};
  }
}
