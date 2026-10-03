// Notifieur SHDM — notifications Web Push, sur le modèle de tvlite-push (TVLite #92).
//
// Fonction SÉPARÉE de celles de TVLite, avec sa propre table : une panne ici n'affecte
// que les notifications SHDM. Elle réutilise les clés VAPID du projet
// (VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY), déjà posées en secrets Supabase.
//
// Routes (POST) :
//   /subscribe    — enregistre l'abonnement de cet appareil (ouvert)
//   /unsubscribe  — le retire
//   /send         — envoie à tous les abonnés ; réservé au workflow GitHub (x-push-secret)
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const supabase = SUPABASE_URL && SERVICE_KEY ? createClient(SUPABASE_URL, SERVICE_KEY) : null;

const VAPID_SUBJECT = "https://jennsen-spec.github.io/shdm-notifier/";
const VAPID_PUBLIC = Deno.env.get("VAPID_PUBLIC_KEY") ?? "";
const VAPID_PRIVATE = Deno.env.get("VAPID_PRIVATE_KEY") ?? "";

// Empreinte SHA-256 du secret d'envoi. Le secret lui-même n'est que dans les secrets
// GitHub (PUSH_SEND_SECRET du dépôt shdm-notifier) : le code public n'en révèle rien.
const SECRET_SHA256 = "3a07bb071726df240d7b654c6f0a3fca0d89bc3b1df539a0f677d0f4592d2774";

const TABLE = "shdm_push_subs";

const cors: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type, x-push-secret",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });

async function sha256(texte: string): Promise<string> {
  const octets = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(texte)));
  return Array.from(octets, (o) => o.toString(16).padStart(2, "0")).join("");
}

interface Abonnement { endpoint: string; p256dh: string; auth: string }

/** Envoie une notification à un abonnement. Renvoie le code HTTP du service de poussée. */
async function envoyer(sub: Abonnement, charge: string): Promise<number> {
  if (!VAPID_PUBLIC || !VAPID_PRIVATE) return 500;
  try {
    const webpush = (await import("npm:web-push@3.6.7")).default;
    webpush.setVapidDetails(VAPID_SUBJECT, VAPID_PUBLIC, VAPID_PRIVATE);
    const res = await webpush.sendNotification(
      { endpoint: sub.endpoint, keys: { p256dh: sub.p256dh, auth: sub.auth } },
      charge,
      { TTL: 24 * 3600 },
    );
    return res.statusCode ?? 201;
  } catch (e) {
    return (e as { statusCode?: number }).statusCode ?? 500;
  }
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "POST requis" }, 405);
  if (!supabase) return json({ error: "base indisponible" }, 503);

  const url = new URL(req.url);
  const body = await req.json().catch(() => null) as Record<string, unknown> | null;

  try {
    if (url.pathname.endsWith("/subscribe")) {
      const ep = body?.endpoint;
      const k = body?.keys as { p256dh?: string; auth?: string } | undefined;
      if (!ep || !k?.p256dh || !k?.auth) return json({ error: "abonnement incomplet" }, 400);
      await supabase.from(TABLE).upsert(
        { endpoint: String(ep), p256dh: String(k.p256dh), auth: String(k.auth) },
        { onConflict: "endpoint" },
      );
      return json({ ok: true });
    }

    if (url.pathname.endsWith("/unsubscribe")) {
      if (!body?.endpoint) return json({ error: "endpoint requis" }, 400);
      await supabase.from(TABLE).delete().eq("endpoint", String(body.endpoint));
      return json({ ok: true });
    }

    if (url.pathname.endsWith("/send")) {
      const secret = req.headers.get("x-push-secret") ?? "";
      if (!secret || (await sha256(secret)) !== SECRET_SHA256) return json({ error: "non autorisé" }, 401);

      const { data: subs } = await supabase.from(TABLE).select("endpoint,p256dh,auth");
      const charge = JSON.stringify({
        titre: (body?.titre as string) ?? "Logements SHDM",
        corps: (body?.corps as string) ?? "",
      });

      let envoyees = 0, expirees = 0, echecs = 0;
      for (const s of (subs ?? []) as Abonnement[]) {
        const code = await envoyer(s, charge);
        if (code === 404 || code === 410) {
          // Abonnement mort (icône supprimée, permission révoquée) → on le retire.
          await supabase.from(TABLE).delete().eq("endpoint", s.endpoint);
          expirees++;
        } else if (code >= 200 && code < 300) envoyees++;
        else echecs++;
      }
      return json({ ok: true, envoyees, expirees, echecs, total: subs?.length ?? 0 });
    }

    return json({ error: "route inconnue" }, 404);
  } catch (e) {
    return json({ error: (e as Error).message }, 500);
  }
});
