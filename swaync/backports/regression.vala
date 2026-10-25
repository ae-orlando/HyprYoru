// Compiled against the actual patched widgets, on a private D-Bus session.
// Author: ae Orland
// GitHub: https://github.com/ae-orlando
namespace SwayNotificationCenter {
    [DBus (name = "org.freedesktop.login1.Session")]
    public class FakeLogin : Object {
        public async void set_brightness (string subsystem, string name, uint32 value) throws Error {
            string root = Environment.get_variable ("YORU_TEST_SYSROOT");
            string calls;
            FileUtils.get_contents (root + "/writes", out calls);
            FileUtils.set_contents (root + "/writes", (int.parse (calls) + 1).to_string ());
            Timeout.add (20, () => { set_brightness.callback (); return Source.REMOVE; });
            yield;
            // Write in place, like sysfs, instead of atomically replacing it.
            var file = FileStream.open (root + "/class/" + subsystem + "/" + name + "/brightness", "w");
            file.printf ("%u", value);
        }
    }

    public class YoruRegression {
        static void pump (int milliseconds = 150) {
            int64 until = get_monotonic_time () + milliseconds * 1000;
            while (get_monotonic_time () < until) {
                while (MainContext.default ().pending ()) {
                    MainContext.default ().iteration (false);
                }
                Thread.usleep (1000);
            }
        }

        static Gtk.Widget? find_css (Gtk.Widget widget, string css) {
            if (widget.has_css_class (css)) {
                return widget;
            }
            for (unowned Gtk.Widget? child = widget.get_first_child (); child != null; child = child.get_next_sibling ()) {
                Gtk.Widget? result = find_css (child, css);
                if (result != null) {
                    return result;
                }
            }
            return null;
        }

        static NotifyParams make_params (uint32 id, string text, string[] actions = {}) {
            var hints = new HashTable<string, Variant> (str_hash, str_equal);
            return new NotifyParams (id, "Yoru regression", 0, "", "Synthetic preview", text, actions, hints, 600000);
        }

        static void notifications () {
            string[] samples = {
                string.nfill (18000, 'a'),
                string.joinv ("\n", Collections.n_copies (40, "A paragraph of synthetic text.")),
                "<b>Heading</b>&#10;" + string.joinv ("&#10;", Collections.n_copies (30, "Another paragraph.")),
                string.joinv ("\r\n\u2028\u2029", Collections.n_copies (30, "Unicode separators.")),
                "https://example.invalid/" + string.nfill (6000, 'x'),
                "<span size=\"80000\">Large markup stays out of the toast</span>"
            };
            uint32 id = 1;
            foreach (string text in samples) {
                NotifyParams param = make_params (id++, text);
                var toast = new Notification.timed (param, NotificationType.FLOATING, 600, 600, 600);
                var body = (Gtk.Label) find_css (toast, "body");
                assert (body != null);
                assert (body.get_text ().validate ());
                string parsed;
                Pango.AttrList attrs;
                try {
                    Pango.parse_markup (text, -1, 0, out attrs, out parsed, null);
                    string expected = new Regex ("\\R+").replace_literal (parsed, -1, 0, " ");
                    assert (body.get_text () == expected);
                } catch (Error error) { assert_not_reached (); }
                Pango.Layout layout = body.get_layout ();
                layout.set_width (300 * Pango.SCALE);
                layout.set_height (-5);
                assert (layout.get_line_count () <= 5);
                assert (body.get_attributes () == null);
                assert (body.get_text ().index_of ("\n") < 0);
                assert (param.body == text);
                var center = new Notification.regular (param, NotificationType.CONTROL_CENTER);
                var full_body = (Gtk.Label) find_css (center, "body");
                assert (full_body.get_lines () == -1);
                assert (full_body.get_ellipsize () == Pango.EllipsizeMode.NONE);
                assert (full_body.get_text () == parsed);
                assert (param.body == text);
                toast.remove_noti_timeout ();
            }
            stdout.printf ("PASS: long text, paragraphs, encoded breaks, Unicode, URLs, markup; full center bodies\n");

            var window = new NotificationWindow ();
            app.add_window (window);
            var pixbuf = new Gdk.Pixbuf (Gdk.Colorspace.RGB, false, 8, 160, 1600);
            pixbuf.fill ((uint32) 0x887766ff);
            string image = Environment.get_variable ("YORU_TEST_SYSROOT") + "/image.png";
            try { pixbuf.save (image, "png"); } catch (Error error) { assert_not_reached (); }
            for (int i = 0; i < 6; i++) {
                var param = make_params (id++, samples[1] + "<img src=\"" + image + "\"/>",
                    {"first", string.nfill (1000, 'L'), "second", "Open", "third", "Later"});
                window.add_notification (param);
            }
            pump (500);
            var scroll = (Gtk.ScrolledWindow) window.get_child ();
            assert (scroll.get_max_content_height () <= 300);
            assert (scroll.get_height () <= 300);
            assert (scroll.get_width () <= 420);
            window.remove_all_notifications (false, null);
            window.destroy ();
            pump (50);
            stdout.printf ("PASS: stacked popups, tall images, and long action labels stay in a 300px viewport\n");
        }

        static string sysroot () { return Environment.get_variable ("YORU_TEST_SYSROOT"); }

        static int read_int (string name) {
            string value;
            try { FileUtils.get_contents (sysroot () + "/" + name, out value); }
            catch (Error error) { assert_not_reached (); }
            return int.parse (value);
        }

        static void external_brightness (int value) {
            var file = FileStream.open (sysroot () + "/class/backlight/test/brightness", "w");
            file.printf ("%d", value);
        }

        static void backlight () {
            var widget = new Widgets.Backlight ("");
            var slider = (Gtk.Scale) widget.get_last_child ();
            widget.on_cc_visibility_change (true);
            pump ();
            assert ((int) slider.get_value () == 37);
            assert (read_int ("writes") == 0);
            external_brightness (473);
            pump ();
            assert ((int) slider.get_value () == 47);
            assert (read_int ("writes") == 0);
            widget.on_cc_visibility_change (false);
            external_brightness (641);
            pump ();
            widget.on_cc_visibility_change (true);
            pump ();
            assert ((int) slider.get_value () == 64);
            assert (read_int ("writes") == 0);
            external_brightness (523);
            pump ();
            assert ((int) slider.get_value () == 52);
            assert (read_int ("writes") == 0);
            stdout.printf ("PASS: external brightness changes and monitor recreation never write back\n");

            // A drag emits changes continuously, rather than only on release.
            for (int i = 53; i <= 57; i++) {
                slider.set_value (i);
                pump (40);
                assert (read_int ("class/backlight/test/brightness") == i * 10);
            }
            for (int i = 58; i <= 90; i++) {
                slider.set_value (i);
            }
            pump (200);
            assert (read_int ("class/backlight/test/brightness") == 900);
            assert ((int) slider.get_value () == 90);
            int writes = read_int ("writes");
            external_brightness (321);
            pump ();
            assert ((int) slider.get_value () == 32);
            assert (read_int ("writes") == writes);
            widget.on_cc_visibility_change (false);
            stdout.printf ("PASS: continuous drag writes, latest-value coalescing, and key sync after dragging\n");
        }

        public static int main (string[] args) {
            if (args.length > 1 && args[1] == "--fake-login") {
                Bus.own_name (BusType.SESSION, "org.freedesktop.login1", BusNameOwnerFlags.NONE,
                    (connection) => {
                        try { connection.register_object ("/org/freedesktop/login1/session/auto", new FakeLogin ()); }
                        catch (Error error) { assert_not_reached (); }
                    },
                    () => { try { FileUtils.set_contents (sysroot () + "/ready", "ready"); } catch (Error error) {} });
                new MainLoop ().run ();
                return 0;
            }
            Gtk.init ();
            Adw.init ();
            typeof (AnimatedList).ensure ();
            typeof (AnimatedListItem).ensure ();
            typeof (Underlay).ensure ();
            ConfigModel.init (args[1]);
            app = new Swaync (false);
            app.use_layer_shell = true;
            app.has_layer_on_demand = false;
            Functions.init ();
            Functions.load_css (args[2]);
            backlight ();
            notifications ();
            return 0;
        }
    }

    // Avoid bringing in another collection library just for fixture strings.
    public class Collections {
        public static string[] n_copies (int count, string text) {
            string[] result = new string[count];
            for (int i = 0; i < count; i++) { result[i] = text; }
            return result;
        }
    }
}
