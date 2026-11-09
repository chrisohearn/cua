//! Keep synthetic delivery seats out of the existing foreground input path.
//! Preserve the legacy last-advertised-seat choice among ordinary seats.
//!
//! The Hyprland plugin advertises an agent seat only while an isolated-input
//! session uses it (#4257), so one can appear between enumeration roundtrips
//! and still be unnamed when a seat is chosen. A named ordinary seat therefore
//! wins over any unnamed seat; unnamed seats are chosen only when no seat has
//! announced an ordinary name (pre-v2 `wl_seat`).

pub(super) struct Seats<T> {
    entries: Vec<(T, Option<String>)>,
}

impl<T> Default for Seats<T> {
    fn default() -> Self {
        Self {
            entries: Vec::new(),
        }
    }
}

impl<T: Clone + PartialEq> Seats<T> {
    pub(super) fn add(&mut self, seat: T) {
        self.entries.push((seat, None));
    }

    pub(super) fn name(&mut self, seat: &T, name: String) {
        if let Some(entry) = self.entries.iter_mut().find(|entry| &entry.0 == seat) {
            entry.1 = Some(name);
        }
    }

    pub(super) fn selected(&self) -> Option<T> {
        let agent = |name: &str| {
            name == "Cua-Test-Agent"
                || name.starts_with("Cua-Test-Agent-")
                || name == "Cua-Agent"
                || name == "Cua-Agent-2"
        };
        let ordinary = self.entries.iter().rev();
        ordinary
            .clone()
            .find(|entry| entry.1.as_deref().is_some_and(|name| !agent(name)))
            .or_else(|| ordinary.clone().find(|entry| entry.1.is_none()))
            .map(|entry| entry.0.clone())
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
                seats.add(seat);
            }
            seats.name(&1, "seat0".into());
            seats.name(&2, "Cua-Test-Agent".into());
            assert_eq!(seats.selected(), Some(1));
        }
    }

    #[test]
    fn no_primary_seat_refuses_and_legacy_selection_is_preserved() {
        let mut seats = Seats::default();
        seats.add(2);
        seats.name(&2, "Cua-Test-Agent".into());
        assert_eq!(seats.selected(), None);
        seats.add(4);
        seats.name(&4, "Cua-Test-Agent-2".into());
        assert_eq!(seats.selected(), None);
        seats.add(1);
        seats.add(3);
        assert_eq!(seats.selected(), Some(3));
    }

    #[test]
    fn session_seat_advertised_late_and_still_unnamed_never_replaces_primary() {
        // A session-lifetime agent seat can arrive after the user's seat was
        // named and before its own name event is dispatched.
        let mut seats = Seats::default();
        seats.add(1);
        seats.name(&1, "Hyprland".into());
        seats.add(2);
        assert_eq!(seats.selected(), Some(1));
        seats.name(&2, "Cua-Agent".into());
        assert_eq!(seats.selected(), Some(1));
        seats.add(3);
        assert_eq!(seats.selected(), Some(1));
    }

    #[test]
    fn production_seats_never_replace_the_primary_seat() {
        let mut seats = Seats::default();
        for (id, name) in [(1, "seat0"), (2, "Cua-Agent"), (3, "Cua-Agent-2")] {
            seats.add(id);
            seats.name(&id, name.into());
        }
        assert_eq!(seats.selected(), Some(1));
    }
}
