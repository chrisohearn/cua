//! Keep synthetic delivery seats out of the existing foreground input path.
//! Preserve the legacy last-advertised-seat choice among ordinary seats.
//!
//! The Hyprland plugin advertises an agent seat only while an isolated-input
//! session uses it (#4257), so one can appear between enumeration roundtrips
//! and still be unnamed when a seat is chosen. Only a seat bound at version 2 or
//! later can announce a name, so an unnamed modern seat may simply be waiting
//! for its name event and ranks below every ordinary candidate. A pre-v2 seat
//! can never be named; it stays an ordinary candidate, so the last-advertised
//! choice among named ordinary and pre-v2 seats is unchanged.

pub(super) struct Seats<T> {
    entries: Vec<Entry<T>>,
}

struct Entry<T> {
    seat: T,
    version: u32,
    name: Option<String>,
}

impl<T> Default for Seats<T> {
    fn default() -> Self {
        Self {
            entries: Vec::new(),
        }
    }
}

impl<T: Clone + PartialEq> Seats<T> {
    /// `version` is the bound `wl_seat` version; `wl_seat.name` exists since v2.
    pub(super) fn add(&mut self, seat: T, version: u32) {
        self.entries.push(Entry {
            seat,
            version,
            name: None,
        });
    }

    pub(super) fn name(&mut self, seat: &T, name: String) {
        if let Some(entry) = self.entries.iter_mut().find(|entry| &entry.seat == seat) {
            entry.name = Some(name);
        }
    }

    pub(super) fn selected(&self) -> Option<T> {
        let agent = |name: &str| {
            name == "Cua-Test-Agent"
                || name.starts_with("Cua-Test-Agent-")
                || name == "Cua-Agent"
                || name == "Cua-Agent-2"
        };
        let latest_first = self.entries.iter().rev();
        latest_first
            .clone()
            .find(|entry| match entry.name.as_deref() {
                Some(name) => !agent(name),
                None => entry.version < 2,
            })
            .or_else(|| latest_first.clone().find(|entry| entry.name.is_none()))
            .map(|entry| entry.seat.clone())
    }
}

#[cfg(test)]
mod tests {
    use super::Seats;

    #[test]
    fn experimental_seat_never_replaces_primary_after_names_arrive() {
        for order in [[1, 2], [2, 1]] {
            let mut seats = Seats::default();
            for seat in order {
                seats.add(seat, 9);
            }
            seats.name(&1, "seat0".into());
            seats.name(&2, "Cua-Test-Agent".into());
            assert_eq!(seats.selected(), Some(1));
        }
    }

    #[test]
    fn no_primary_seat_refuses_and_legacy_selection_is_preserved() {
        let mut seats = Seats::default();
        seats.add(2, 9);
        seats.name(&2, "Cua-Test-Agent".into());
        assert_eq!(seats.selected(), None);
        seats.add(4, 9);
        seats.name(&4, "Cua-Test-Agent-2".into());
        assert_eq!(seats.selected(), None);
        seats.add(1, 1);
        seats.add(3, 1);
        assert_eq!(seats.selected(), Some(3));
    }

    #[test]
    fn session_seat_advertised_late_and_still_unnamed_never_replaces_primary() {
        // A session-lifetime agent seat can arrive after the user's seat was
        // named and before its own name event is dispatched.
        let mut seats = Seats::default();
        seats.add(1, 9);
        seats.name(&1, "Hyprland".into());
        seats.add(2, 9);
        assert_eq!(seats.selected(), Some(1));
        seats.name(&2, "Cua-Agent".into());
        assert_eq!(seats.selected(), Some(1));
        seats.add(3, 9);
        assert_eq!(seats.selected(), Some(1));
    }

    #[test]
    fn production_seats_never_replace_the_primary_seat() {
        let mut seats = Seats::default();
        for (id, name) in [(1, "seat0"), (2, "Cua-Agent"), (3, "Cua-Agent-2")] {
            seats.add(id, 9);
            seats.name(&id, name.into());
        }
        assert_eq!(seats.selected(), Some(1));
    }

    #[test]
    fn later_pre_v2_seat_keeps_last_advertised_precedence_over_named_seat() {
        // A v1 wl_seat can never send wl_seat.name, so it is an ordinary
        // candidate and the legacy last-advertised choice still applies.
        let mut seats = Seats::default();
        seats.add(1, 9);
        seats.name(&1, "seat0".into());
        seats.add(2, 1);
        assert_eq!(seats.selected(), Some(2));
        // An unnamed modern seat, by contrast, may still be an agent seat.
        seats.add(3, 9);
        assert_eq!(seats.selected(), Some(2));
    }
}
