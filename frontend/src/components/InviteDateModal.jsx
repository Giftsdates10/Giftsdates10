import React, { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { toast } from "sonner";
import { ShieldAlert, Sparkles } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

export default function InviteDateModal({ open, onOpenChange, target }) {
  const { user, lang, refreshUser } = useApp();
  const tr = (k, vars) => { let s = t(k, lang); if (vars) Object.entries(vars).forEach(([n, v]) => (s = s.replace(`{${n}}`, v))); return s; };
  const floor = Math.max(150, target?.date_price || 0);
  const [activities, setActivities] = useState(["", "", ""]);
  const [coins, setCoins] = useState(floor);
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (open) { setActivities(["", "", ""]); setCoins(floor); setAck(false); } }, [open]); // eslint-disable-line

  const setAct = (i, v) => setActivities(a => a.map((x, idx) => idx === i ? v : x));

  const send = async () => {
    const acts = activities.map(a => a.trim());
    if (acts.some(a => !a)) { toast.error(tr("activities_required_err")); return; }
    if (!ack) { toast.error(tr("iv_accept_safety")); return; }
    if (coins < floor) { toast.error(tr("iv_min_is", { n: floor })); return; }
    if (((user?.coins || 0) + (user?.withdrawable || 0)) < coins) { toast.error(tr("not_enough_coins")); return; }
    setBusy(true);
    try {
      await api.post("/invites", {
        recipient_id: target.id,
        activity_option_1: acts[0], activity_option_2: acts[1], activity_option_3: acts[2],
        coins, safety_ack: true,
      });
      await refreshUser();
      toast.success(tr("iv_sent_success"));
      onOpenChange(false);
    } catch (e) {
      const d = e.response?.data?.detail || "";
      toast.error(d === "ACTIVITIES_REQUIRED" ? tr("activities_required_err")
        : d.startsWith("MIN_COINS:") ? tr("iv_min_is", { n: d.split(":")[1] })
        : d || tr("failed"));
    } finally { setBusy(false); }
  };

  const allFilled = activities.every(a => a.trim());

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#161320] border-white/10 text-white max-w-lg max-h-[90vh] overflow-y-auto" data-testid="invite-date-modal">
        <DialogHeader>
          <DialogTitle className="font-serif-luxe text-2xl">{tr("iv_title", { name: target?.name })}</DialogTitle>
          <DialogDescription className="text-slate-400 text-sm">{tr("date_ideas_hint")}</DialogDescription>
        </DialogHeader>

        <div className="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200/90" data-testid="invite-safety-notice">
          <ShieldAlert size={16} className="mt-0.5 shrink-0 text-amber-300" />
          <span>{tr("iv_safety")}</span>
        </div>

        <div className="space-y-3" data-testid="invite-activities">
          <div className="flex items-center gap-2 text-sm text-slate-200">
            <Sparkles size={15} className="text-rose-300" />
            <span className="font-semibold">{tr("date_ideas_label")}</span>
          </div>
          {[0, 1, 2].map(i => (
            <div key={i}>
              <label className="text-xs text-slate-400">{tr("date_idea_slot", { n: i + 1 })}</label>
              <Input
                data-testid={`invite-activity-${i}`}
                value={activities[i]}
                onChange={e => setAct(i, e.target.value)}
                placeholder={tr(`date_idea_ph_${i}`)}
                maxLength={120}
                className="bg-white/5 border-white/10 mt-1"
              />
            </div>
          ))}
        </div>

        <div className="grid sm:grid-cols-2 gap-3 items-end pt-2 border-t border-white/10">
          <div>
            <label className="text-xs text-slate-400">{tr("iv_coins_label", { n: floor })}</label>
            <Input data-testid="invite-coins" type="number" min={floor} step="50" value={coins} onChange={e => setCoins(parseInt(e.target.value || 0))} className="bg-white/5 border-white/10 mt-1" />
          </div>
          <label className="flex items-start gap-2 text-xs text-slate-300 cursor-pointer" data-testid="invite-ack">
            <input type="checkbox" checked={ack} onChange={e => setAck(e.target.checked)} className="mt-0.5" />
            {tr("iv_ack_label")}
          </label>
        </div>

        <Button data-testid="invite-send-button" disabled={busy || !allFilled || !ack} onClick={send} className="rose-btn text-white border-0 w-full h-11">
          {tr("iv_send")} · 🪙 {coins}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
