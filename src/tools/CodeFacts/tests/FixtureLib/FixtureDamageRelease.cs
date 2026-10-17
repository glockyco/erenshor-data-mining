using System.Collections.Generic;

namespace FixtureLib
{
    public class FixtureDamageRelease
    {
        public FixtureDamageRelease Protector;
        public FixtureDamageRelease Holder;
        public FixtureDamageRelease Dialog;
        public bool ActiveSelf;
        public bool ActiveInHierarchy;
        public bool Invulnerable;
        public bool DropInvulnOnHolder;
        public List<FixtureDamageRelease> DryTargets = new List<FixtureDamageRelease>();
        public List<FixtureDamageRelease> WetTargets = new List<FixtureDamageRelease>();
        public List<FixtureDamageRelease> Quests = new List<FixtureDamageRelease>();
        public int CurrentHP;
        public int ShiftAtLife;
        public float PhaseDelay;

        public void ProtectorRelease()
        {
            if (Protector != null && Protector.ActiveSelf)
            {
                Invulnerable = true;
            }
            else
            {
                Invulnerable = false;
            }
        }

        public void ProtectorReleaseChangedActivity()
        {
            if (Protector != null && Protector.ActiveInHierarchy)
            {
                Invulnerable = true;
            }
            else
            {
                Invulnerable = false;
            }
        }

        public void ProtectorReleaseChangedNull()
        {
            if (Protector == null || Protector.ActiveSelf)
            {
                Invulnerable = true;
            }
            else
            {
                Invulnerable = false;
            }
        }

        public void WeatherRelease()
        {
            foreach (FixtureDamageRelease target in DryTargets)
            {
                target.ActiveSelf = false;
            }
            foreach (FixtureDamageRelease target2 in WetTargets)
            {
                target2.ActiveSelf = true;
            }
        }

        public void WeatherReleaseChangedOrder()
        {
            foreach (FixtureDamageRelease target2 in WetTargets)
            {
                target2.ActiveSelf = true;
            }
            foreach (FixtureDamageRelease target in DryTargets)
            {
                target.ActiveSelf = false;
            }
        }

        public void TradeRelease()
        {
            foreach (FixtureDamageRelease quest in Holder.Quests)
            {
                if (quest.DropInvulnOnHolder)
                {
                    Holder.Invulnerable = false;
                }
            }
        }

        public void TradeReleaseChangedHolder()
        {
            foreach (FixtureDamageRelease quest in Dialog.Quests)
            {
                if (quest.DropInvulnOnHolder)
                {
                    Holder.Invulnerable = false;
                }
            }
        }

        public void HealthPhaseRelease()
        {
            if (CurrentHP < ShiftAtLife)
            {
                PhaseDelay = 200f;
            }
            if (PhaseDelay > 0f)
            {
                PhaseDelay -= 1f;
                if (PhaseDelay <= 0f)
                {
                    Invulnerable = false;
                }
            }
        }

        public void HealthPhaseReleaseChangedBootstrap()
        {
            if (CurrentHP > ShiftAtLife)
            {
                PhaseDelay = 200f;
            }
            if (PhaseDelay > 0f)
            {
                PhaseDelay -= 1f;
                if (PhaseDelay <= 0f)
                {
                    Invulnerable = false;
                }
            }
        }
    }
}
