#include <gtk/gtk.h>
#include <curl/curl.h>
#include <json-glib/json-glib.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define BASE "http://127.0.0.1:8756"
#define MAX_LEVELS 4096
#define WIDTH 660
#define RADIUS 30

static char TOKEN[128];
static CURL *CURL_H;

typedef struct {
    GtkWidget *window;
    GtkWidget *root;
    GtkWidget *title;
    GtkWidget *wave;
    GtkWidget *stack;
    GtkWidget *timer;
    GtkWidget *phase;
    GtkWidget *progress;
    GtkWidget *error_label;
    GtkWidget *transcript;
    GtkWidget *mic_box;
    GtkWidget *lang_box;
    GtkWidget *copy_btn;
    GtkWidget *scroll;

    double levels[MAX_LEVELS];
    int nlevels;
    int listening;

    char status[32];
    double duration;
    double progress_value;
    int has_progress;
    int visible;
    int last_reveal;
    int last_hide;
    int poll_ready;
} App;

static App A;
static int work_progress_pct = -1;
static int RENDER_MODE = 0;

static size_t write_cb(void *ptr, size_t size, size_t nmemb, void *userdata) {
    GString *s = userdata;
    g_string_append_len(s, ptr, size * nmemb);
    return size * nmemb;
}

static GString *http_request(const char *path, const char *body) {
    GString *out = g_string_new(NULL);
    char url[512];
    snprintf(url, sizeof url, "%s%s", BASE, path);
    curl_easy_reset(CURL_H);
    curl_easy_setopt(CURL_H, CURLOPT_URL, url);
    curl_easy_setopt(CURL_H, CURLOPT_WRITEFUNCTION, write_cb);
    curl_easy_setopt(CURL_H, CURLOPT_WRITEDATA, out);
    curl_easy_setopt(CURL_H, CURLOPT_TIMEOUT_MS, 400L);
    curl_easy_setopt(CURL_H, CURLOPT_NOSIGNAL, 1L);
    struct curl_slist *headers = NULL;
    char auth[256];
    snprintf(auth, sizeof auth, "X-Silisten-Token: %s", TOKEN);
    headers = curl_slist_append(headers, auth);
    if (body) {
        headers = curl_slist_append(headers, "Content-Type: application/json");
        curl_easy_setopt(CURL_H, CURLOPT_POSTFIELDS, body);
    }
    curl_easy_setopt(CURL_H, CURLOPT_HTTPHEADER, headers);
    curl_easy_perform(CURL_H);
    curl_slist_free_all(headers);
    return out;
}

static void post(const char *path, const char *json) {
    GString *r = http_request(path, json ? json : "{}");
    g_string_free(r, TRUE);
}

static void read_token(void) {
    const char *home = g_get_home_dir();
    char path[512];
    snprintf(path, sizeof path, "%s/.config/silisten/token", home);
    FILE *f = fopen(path, "r");
    if (!f) return;
    if (fgets(TOKEN, sizeof TOKEN, f)) g_strchomp(TOKEN);
    fclose(f);
}

static void draw_notch(cairo_t *cr, int width, int height) {
    cairo_set_operator(cr, CAIRO_OPERATOR_SOURCE);
    cairo_set_source_rgba(cr, 0, 0, 0, 0);
    cairo_paint(cr);
    cairo_set_operator(cr, CAIRO_OPERATOR_OVER);

    double r = RADIUS;
    cairo_new_sub_path(cr);
    cairo_arc(cr, r, r, r, M_PI, 1.5 * M_PI);
    cairo_arc(cr, width - r, r, r, 1.5 * M_PI, 2 * M_PI);
    cairo_line_to(cr, width, height);
    cairo_line_to(cr, 0, height);
    cairo_close_path(cr);
    cairo_set_source_rgb(cr, 0, 0, 0);
    cairo_fill(cr);

    cairo_set_line_width(cr, 1.0);
    cairo_set_source_rgba(cr, 1, 1, 1, 0.10);
    cairo_new_sub_path(cr);
    cairo_arc(cr, r, r, r, M_PI, 1.5 * M_PI);
    cairo_arc(cr, width - r, r, r, 1.5 * M_PI, 2 * M_PI);
    cairo_stroke(cr);
}

static void draw_background(GtkWidget *w, cairo_t *cr, gpointer data) {
    (void)data;
    draw_notch(cr, gtk_widget_get_allocated_width(w), gtk_widget_get_allocated_height(w));
}

static void draw_wave(GtkWidget *w, cairo_t *cr, gpointer data) {
    (void)data;
    int width = gtk_widget_get_allocated_width(w);
    int height = gtk_widget_get_allocated_height(w);
    int bars = width / 6;
    if (bars < 8) bars = 8;

    cairo_set_source_rgb(cr, 0.96, 0.96, 0.97);
    double gap = 3.5;
    double bw = ((double)width - gap * (bars - 1)) / bars;
    if (bw < 1.5) bw = 1.5;
    double mid = height / 2.0;

    for (int i = 0; i < bars; i++) {
        double v = 0.0;
        if (A.listening && A.nlevels > 0) {
            int from = (int)((double)i / bars * A.nlevels);
            int to = (int)((double)(i + 1) / bars * A.nlevels);
            if (to <= from) to = from + 1;
            double sum = 0;
            int count = 0;
            for (int j = from; j < to && j < A.nlevels; j++) {
                sum += A.levels[j];
                count++;
            }
            v = count ? sum / count : 0;
        }
        double h = 3.0 + pow(v, 0.7) * height * 0.86;
        if (h > height) h = height;
        double x = i * (bw + gap) + bw / 2.0;
        double half = h / 2.0;
        cairo_set_line_width(cr, bw);
        cairo_set_line_cap(cr, CAIRO_LINE_CAP_ROUND);
        cairo_move_to(cr, x, mid - half + bw / 2.0);
        cairo_line_to(cr, x, mid + half - bw / 2.0);
        cairo_stroke(cr);
    }
}

static void fit_transcript(void) {
}

static char current_page[16] = "";

static int target_height(void) {
    const char *page = current_page[0] ? current_page : "result";
    int h;
    if (strcmp(page, "listen") == 0) h = 198;
    else if (strcmp(page, "work") == 0) h = 150;
    else if (strcmp(page, "error") == 0) h = 190;
    else h = 420;
    return h;
}

static void monitor_geom(GdkRectangle *geo) {
    GdkDisplay *dpy = gdk_display_get_default();
    GdkMonitor *mon = gdk_display_get_primary_monitor(dpy);
    if (!mon) mon = gdk_display_get_monitor(dpy, 0);
    gdk_monitor_get_geometry(mon, geo);
}

static void place(int height, int y_offset) {
    GdkRectangle geo;
    monitor_geom(&geo);
    int x = geo.x + (geo.width - WIDTH) / 2;
    int y = geo.y + geo.height - height + y_offset;
    gtk_widget_set_size_request(A.window, WIDTH, height);
    gtk_window_resize(GTK_WINDOW(A.window), WIDTH, height);
    gtk_window_move(GTK_WINDOW(A.window), x, y);
    {
        GtkAllocation wa;
        gtk_widget_get_allocation(A.window, &wa);
        fprintf(stderr, "[place] want %dx%d  win alloc %dx%d at %d,%d\n", WIDTH, height, wa.width, wa.height, wa.x, wa.y);
    }
}

static void repaint(void) {
    gtk_widget_queue_draw(A.window);
    gtk_widget_queue_draw(A.root);
    GdkWindow *gw = gtk_widget_get_window(A.window);
    if (gw) {
        gdk_window_invalidate_rect(gw, NULL, TRUE);
        gdk_window_process_updates(gw, TRUE);
    }
    while (gtk_events_pending()) gtk_main_iteration();
}

static void fit_window(void) {
    place(target_height(), 0);
    repaint();
}

static gdouble anim_pos = 1.0;
static gdouble anim_vel = 0.0;
static int anim_dir = 0;
static int anim_height = 0;
static guint anim_id = 0;

static gboolean anim_tick(gpointer d) {
    (void)d;
    const gdouble stiffness = 260.0;
    const gdouble damping = 26.0;
    gdouble target = anim_dir > 0 ? 1.0 : 0.0;
    gdouble dt = 1.0 / 60.0;
    gdouble force = (target - anim_pos) * stiffness - anim_vel * damping;
    anim_vel += force * dt;
    anim_pos += anim_vel * dt;

    if (fabs(anim_pos - target) < 0.004 && fabs(anim_vel) < 0.5) {
        anim_pos = target;
        anim_vel = 0;
        anim_id = 0;
        if (anim_dir > 0) {
            place(anim_height, 0);
            gtk_widget_set_opacity(A.window, 1.0);
            repaint();
        } else {
            gtk_widget_hide(A.window);
            gtk_widget_set_opacity(A.window, 1.0);
        }
        return G_SOURCE_REMOVE;
    }

    int slide = (int)(anim_pos * anim_height);
    place(anim_height, anim_height - slide);
    gtk_widget_set_opacity(A.window, CLAMP(anim_pos, 0.0, 1.0));
    repaint();
    return G_SOURCE_CONTINUE;
}

static void animate(int open) {
    anim_height = target_height();
    anim_dir = open ? 1 : -1;
    if (open) {
        anim_pos = 0.0;
        anim_vel = 0.0;
        gtk_widget_set_opacity(A.window, 0.0);
        gtk_widget_show_all(A.window);
    }
    anim_vel = open ? 6.0 : -6.0;
    if (!anim_id) anim_id = g_timeout_add(16, anim_tick, NULL);
}

static void show_page(const char *name) {
    if (strcmp(current_page, name) == 0) return;
    g_strlcpy(current_page, name, sizeof current_page);
    gtk_stack_set_visible_child_name(GTK_STACK(A.stack), name);
    if (!gtk_widget_get_visible(A.window)) {
        fit_window();
        return;
    }
    int h = target_height();
    anim_height = h;
    place(h, 0);
    repaint();
}

static void on_done(GtkWidget *b, gpointer d) {
    (void)b;
    (void)d;
    post("/record/stop", "{}");
}

static void on_copy(GtkWidget *b, gpointer d) {
    (void)d;
    GtkClipboard *cb = gtk_clipboard_get(GDK_SELECTION_CLIPBOARD);
    const char *text = gtk_label_get_text(GTK_LABEL(A.transcript));
    if (text && *text) {
        gtk_clipboard_set_text(cb, text, -1);
        gtk_button_set_label(GTK_BUTTON(b), "Copied");
        g_timeout_add(800, (GSourceFunc)gtk_widget_hide, A.window);
    }
}

static void on_more(GtkWidget *b, gpointer d) {
    (void)b;
    (void)d;
    post("/record/start", "{\"append\":true}");
}

static void on_file(GtkWidget *b, gpointer d) {
    (void)b;
    (void)d;
    GtkWidget *dialog = gtk_file_chooser_dialog_new(
        "Transcribe file", GTK_WINDOW(A.window), GTK_FILE_CHOOSER_ACTION_OPEN,
        "Cancel", GTK_RESPONSE_CANCEL, "Open", GTK_RESPONSE_ACCEPT, NULL);
    if (gtk_dialog_run(GTK_DIALOG(dialog)) == GTK_RESPONSE_ACCEPT) {
        char *path = gtk_file_chooser_get_filename(GTK_FILE_CHOOSER(dialog));
        if (path) {
            JsonBuilder *jb = json_builder_new();
            json_builder_begin_object(jb);
            json_builder_set_member_name(jb, "path");
            json_builder_add_string_value(jb, path);
            json_builder_set_member_name(jb, "append");
            gboolean has = g_strcmp0(gtk_label_get_text(GTK_LABEL(A.transcript)), "") != 0;
            json_builder_add_boolean_value(jb, has);
            json_builder_end_object(jb);
            JsonGenerator *g = json_generator_new();
            JsonNode *node = json_builder_get_root(jb);
            json_generator_set_root(g, node);
            char *payload = json_generator_to_data(g, NULL);
            post("/upload", payload);
            g_free(payload);
            json_node_free(node);
            g_object_unref(g);
            g_object_unref(jb);
            g_free(path);
        }
    }
    gtk_widget_destroy(dialog);
}

static void on_close(GtkWidget *b, gpointer d) {
    (void)b;
    (void)d;
    gtk_widget_hide(A.window);
    post("/ui", "{\"visible\":false}");
}

static gboolean on_key(GtkWidget *w, GdkEventKey *e, gpointer d) {
    (void)w;
    (void)d;
    if (e->keyval == GDK_KEY_Escape) {
        gtk_widget_hide(A.window);
        return TRUE;
    }
    return FALSE;
}

static void populate_mic(void) {
    GString *r = http_request("/sources", NULL);
    JsonParser *p = json_parser_new();
    gtk_combo_box_text_remove_all(GTK_COMBO_BOX_TEXT(A.mic_box));
    gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(A.mic_box), "default", "Default mic");
    if (json_parser_load_from_data(p, r->str, -1, NULL)) {
        JsonArray *arr = json_node_get_array(json_parser_get_root(p));
        for (guint i = 0; i < json_array_get_length(arr); i++) {
            JsonObject *o = json_array_get_object_element(arr, i);
            const char *id = json_object_get_string_member(o, "id");
            const char *label = json_object_get_string_member(o, "label");
            gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(A.mic_box), id, label);
        }
        fprintf(stderr, "[mic] %u sources\n", json_array_get_length(arr));
    } else {
        fprintf(stderr, "[mic] parse failed: %.120s\n", r->str);
    }
    g_object_unref(p);
    g_string_free(r, TRUE);
    gtk_combo_box_set_active(GTK_COMBO_BOX(A.mic_box), 0);
}

static void populate_lang(void) {
    GString *r = http_request("/languages", NULL);
    JsonParser *p = json_parser_new();
    gtk_combo_box_text_remove_all(GTK_COMBO_BOX_TEXT(A.lang_box));
    if (json_parser_load_from_data(p, r->str, -1, NULL)) {
        JsonArray *arr = json_node_get_array(json_parser_get_root(p));
        for (guint i = 0; i < json_array_get_length(arr); i++) {
            JsonObject *o = json_array_get_object_element(arr, i);
            const char *code = json_object_get_string_member(o, "code");
            const char *name = json_object_get_string_member(o, "name");
            gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(A.lang_box), code, name);
        }
        fprintf(stderr, "[lang] %u languages\n", json_array_get_length(arr));
    } else {
        fprintf(stderr, "[lang] parse failed: %.120s\n", r->str);
    }
    gtk_combo_box_set_active(GTK_COMBO_BOX(A.lang_box), 0);
    g_object_unref(p);
    g_string_free(r, TRUE);
}

static void on_mic_changed(GtkComboBox *c, gpointer d) {
    (void)d;
    const char *id = gtk_combo_box_get_active_id(c);
    if (!id) return;
    JsonBuilder *jb = json_builder_new();
    json_builder_begin_object(jb);
    json_builder_set_member_name(jb, "input_device");
    json_builder_add_string_value(jb, id);
    json_builder_end_object(jb);
    JsonGenerator *g = json_generator_new();
    JsonNode *node = json_builder_get_root(jb);
    json_generator_set_root(g, node);
    char *payload = json_generator_to_data(g, NULL);
    post("/config", payload);
    g_free(payload);
    json_node_free(node);
    g_object_unref(g);
    g_object_unref(jb);
}

static void on_lang_changed(GtkComboBox *c, gpointer d) {
    (void)d;
    const char *code = gtk_combo_box_get_active_id(c);
    if (!code) return;
    JsonBuilder *jb = json_builder_new();
    json_builder_begin_object(jb);
    json_builder_set_member_name(jb, "language");
    json_builder_add_string_value(jb, code);
    json_builder_end_object(jb);
    JsonGenerator *g = json_generator_new();
    JsonNode *node = json_builder_get_root(jb);
    json_generator_set_root(g, node);
    char *payload = json_generator_to_data(g, NULL);
    post("/config", payload);
    g_free(payload);
    json_node_free(node);
    g_object_unref(g);
    g_object_unref(jb);
}

static void apply_state(const char *json) {
    JsonParser *p = json_parser_new();
    if (!json_parser_load_from_data(p, json, -1, NULL)) {
        g_object_unref(p);
        return;
    }
    JsonNode *root = json_parser_get_root(p);
    if (!root || !JSON_NODE_HOLDS_OBJECT(root)) {
        g_object_unref(p);
        return;
    }
    JsonObject *o = json_node_get_object(root);

    static int ensured = 0;
    if (!ensured && gtk_combo_box_get_active(GTK_COMBO_BOX(A.lang_box)) < 0) {
        ensured = 1;
        populate_lang();
        populate_mic();
    } else if (gtk_combo_box_get_active(GTK_COMBO_BOX(A.lang_box)) >= 0) {
        ensured = 1;
    }

    const char *status = json_object_get_string_member(o, "status");
    if (!status) status = "idle";
    g_strlcpy(A.status, status, sizeof A.status);
    A.duration = json_object_get_double_member(o, "duration");
    A.listening = strcmp(status, "listening") == 0;

    if (json_object_has_member(o, "progress") && !json_object_get_null_member(o, "progress")) {
        A.progress_value = json_object_get_double_member(o, "progress");
        A.has_progress = 1;
    } else {
        A.has_progress = 0;
    }

    static int dbg = 0;
    if (++dbg % 120 == 0) fprintf(stderr, "[dbg] nlevels=%d listening=%d\n", A.nlevels, A.listening);
    JsonNode *lv = json_object_get_member(o, "levels");
    if (lv && JSON_NODE_HOLDS_ARRAY(lv)) {
        JsonArray *arr = json_node_get_array(lv);
        for (guint i = 0; i < json_array_get_length(arr); i++) {
            if (A.nlevels < MAX_LEVELS) A.levels[A.nlevels++] = json_array_get_double_element(arr, i);
        }
    }

    int reveal = json_object_has_member(o, "reveal") ? json_object_get_int_member(o, "reveal") : 0;
    int hide = json_object_has_member(o, "hide_request") ? json_object_get_int_member(o, "hide_request") : 0;
    if (A.poll_ready && reveal != A.last_reveal) {
        animate(1);
    }
    if (A.poll_ready && hide != A.last_hide) animate(0);
    A.last_reveal = reveal;
    A.last_hide = hide;
    A.poll_ready = 1;

    const char *text = json_object_has_member(o, "text") ? json_object_get_string_member(o, "text") : "";
    if (text && *text) {
        gtk_label_set_text(GTK_LABEL(A.transcript), text);
        gtk_style_context_remove_class(gtk_widget_get_style_context(A.transcript), "empty");
        gtk_scrolled_window_set_min_content_height(GTK_SCROLLED_WINDOW(A.scroll), 240);
    gtk_scrolled_window_set_max_content_height(GTK_SCROLLED_WINDOW(A.scroll), 240);
    gtk_scrolled_window_set_propagate_natural_height(GTK_SCROLLED_WINDOW(A.scroll), FALSE);
    } else if (strcmp(status, "done") == 0 || strcmp(status, "idle") == 0) {
        gtk_label_set_text(GTK_LABEL(A.transcript), "No speech detected. Try again.");
        gtk_style_context_add_class(gtk_widget_get_style_context(A.transcript), "empty");
        gtk_scrolled_window_set_min_content_height(GTK_SCROLLED_WINDOW(A.scroll), 28);
    gtk_scrolled_window_set_max_content_height(GTK_SCROLLED_WINDOW(A.scroll), 28);
    }

    const char *phase = json_object_has_member(o, "phase") ? json_object_get_string_member(o, "phase") : "";
    if (strcmp(status, "thinking") == 0) {
        if (phase && strcmp(phase, "identifying speakers") == 0)
            gtk_label_set_text(GTK_LABEL(A.phase), "Working out who is speaking");
        else if (phase && strcmp(phase, "decoding") == 0)
            gtk_label_set_text(GTK_LABEL(A.phase), "Opening the file");
        else
            gtk_label_set_text(GTK_LABEL(A.phase), "Turning your voice into text");
        work_progress_pct = A.has_progress ? (int)(A.progress_value * 100.0) : -1;
        gtk_widget_queue_draw(A.progress);
    }

    fit_transcript();

    const char *title = "Listening";
    if (strcmp(status, "thinking") == 0) title = "Transcribing";
    else if (strcmp(status, "error") == 0) title = "Something went wrong";
    else if (strcmp(status, "done") == 0 || strcmp(status, "idle") == 0) title = "Transcription";
    gtk_label_set_text(GTK_LABEL(A.title), title);
    if (gtk_widget_get_visible(A.window) && anim_id == 0) {
        int want = target_height();
        GtkAllocation wa;
        gtk_widget_get_allocation(A.window, &wa);
        if (want != wa.height) {
            place(want, 0);
            repaint();
        }
    }

    if (strcmp(status, "error") == 0) {
        const char *err = json_object_has_member(o, "error") ? json_object_get_string_member(o, "error") : "";
        gtk_label_set_text(GTK_LABEL(A.error_label), err && *err ? err : "Something went wrong.");
    }

    char timer[32];
    if (A.listening) {
        int total = (int)A.duration;
        snprintf(timer, sizeof timer, "%d:%02d", total / 60, total % 60);
        gtk_label_set_text(GTK_LABEL(A.timer), timer);
        gtk_widget_set_sensitive(A.copy_btn, FALSE);
        show_page("listen");
    } else if (strcmp(status, "thinking") == 0) {
        show_page("work");
    } else if (strcmp(status, "error") == 0) {
        show_page("error");
    } else {
        gtk_widget_set_sensitive(A.copy_btn, text && *text);
        show_page("result");
    }

    gint active;
    if (json_object_has_member(o, "config")) {
        JsonObject *cfg = json_object_get_object_member(o, "config");
        if (cfg && json_object_has_member(cfg, "language")) {
            const char *lang = json_object_get_string_member(cfg, "language");
            if (!gtk_combo_box_set_active_id(GTK_COMBO_BOX(A.lang_box), lang && *lang ? lang : "")) {
                gtk_combo_box_set_active(GTK_COMBO_BOX(A.lang_box), 0);
            }
        }
        if (cfg && json_object_has_member(cfg, "input_device")) {
            const char *dev = json_object_get_string_member(cfg, "input_device");
            if (!gtk_combo_box_set_active_id(GTK_COMBO_BOX(A.mic_box), dev && *dev ? dev : "default")) {
                gtk_combo_box_set_active(GTK_COMBO_BOX(A.mic_box), 0);
            }
        }
    }
    (void)active;

    g_object_unref(p);
}

static gboolean on_tick(gpointer d) {
    (void)d;
    char path[64];
    int vis = (anim_dir >= 0 && anim_pos > 0.5 && gtk_widget_get_mapped(A.window)) ? 1 : 0;
    snprintf(path, sizeof path, "/state?levels=1&visible=%d", vis);
    GString *r = http_request(path, NULL);
    if (r->len > 0) apply_state(r->str);
    g_string_free(r, TRUE);
    gtk_widget_queue_draw(A.wave);
    return G_SOURCE_CONTINUE;
}

static void load_css(void) {
    GtkCssProvider *css = gtk_css_provider_new();
    const char *data =
        "window { background-color: transparent; }\n"
        "label { color: #f5f5f7; font-family: Inter, \"Ubuntu Sans\", sans-serif; font-size: 17px; }\n"
        "button label { color: inherit; font-size: 15px; font-weight: 600; }\n"
        "combobox label { color: #d8d8dc; font-size: 15px; }\n"
        ".title { font-size: 27px; font-weight: 600; }\n"
        ".timer { font-size: 46px; font-weight: 500; }\n"
        ".muted { color: #8e8e93; font-size: 15px; }\n"
        "label.empty { color: #6e6e73; }\n"
        "button { border-radius: 999px; padding: 9px 20px; font-size: 15px; font-weight: 600;\n"
        "         background-image: none; box-shadow: none; border: none; }\n"
        "button.primary { background-color: #f5f5f7; color: #000; }\n"
        "button.primary label { color: #000; }\n"
        "button.primary:hover { background-color: #ffffff; }\n"
        "button.ghost { background-color: rgba(255,255,255,0.10); color: #f5f5f7; font-weight: 500; }\n"
        "button.ghost:hover { background-color: rgba(255,255,255,0.16); }\n"
        "combobox { border-radius: 999px; background-color: rgba(255,255,255,0.10);\n"
        "           color: #d8d8dc; padding: 2px 6px; font-size: 15px; min-width: 110px; }\n"
        "combobox button { background-color: transparent; padding: 2px 6px; color: #d8d8dc;\n"
        "                  min-height: 20px; border-radius: 999px; }\n"
        "combobox arrow { min-width: 12px; min-height: 12px; }\n"
        "progressbar trough { min-height: 3px; border-radius: 3px; background-color: rgba(255,255,255,0.12); }\n"
        "progressbar progress { min-height: 3px; border-radius: 3px; background-color: #f5f5f7; }\n"
        "textview, textview text { background-color: transparent; color: #f5f5f7; font-size: 18px; }\n"
        "scrolledwindow { border: none; box-shadow: none; }\n"
        "scrolledwindow:focus, textview:focus { outline: none; border: none; box-shadow: none; }\n";
    gtk_css_provider_load_from_data(css, data, -1, NULL);
    gtk_style_context_add_provider_for_screen(
        gdk_screen_get_default(), GTK_STYLE_PROVIDER(css), GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    g_object_unref(css);
}

static GtkWidget *pane_listen(void) {
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 6);
    A.timer = gtk_label_new("0:00");
    gtk_widget_set_halign(A.timer, GTK_ALIGN_START);
    gtk_style_context_add_class(gtk_widget_get_style_context(A.timer), "timer");
    gtk_box_pack_start(GTK_BOX(box), A.timer, FALSE, FALSE, 0);

    A.wave = gtk_drawing_area_new();
    gtk_widget_set_size_request(A.wave, -1, 80);
    g_signal_connect(A.wave, "draw", G_CALLBACK(draw_wave), NULL);
    gtk_box_pack_start(GTK_BOX(box), A.wave, FALSE, FALSE, 0);

    GtkWidget *row = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 10);
    gtk_widget_set_size_request(row, WIDTH - 40, -1);
    GtkWidget *done = gtk_button_new_with_label("Done");
    gtk_style_context_add_class(gtk_widget_get_style_context(done), "primary");
    g_signal_connect(done, "clicked", G_CALLBACK(on_done), NULL);
    gtk_widget_set_valign(done, GTK_ALIGN_CENTER);
    gtk_box_pack_start(GTK_BOX(row), done, FALSE, FALSE, 0);

    A.mic_box = gtk_combo_box_text_new();
    g_signal_connect(A.mic_box, "changed", G_CALLBACK(on_mic_changed), NULL);
    gtk_widget_set_size_request(A.mic_box, 210, -1);
    gtk_widget_set_hexpand(A.mic_box, FALSE);
    gtk_widget_set_halign(A.mic_box, GTK_ALIGN_END);
    gtk_box_pack_end(GTK_BOX(row), A.mic_box, FALSE, FALSE, 0);

    A.lang_box = gtk_combo_box_text_new();
    g_signal_connect(A.lang_box, "changed", G_CALLBACK(on_lang_changed), NULL);
    gtk_widget_set_size_request(A.lang_box, 150, -1);
    gtk_widget_set_halign(A.lang_box, GTK_ALIGN_END);
    gtk_box_pack_end(GTK_BOX(row), A.lang_box, FALSE, FALSE, 0);

    gtk_box_pack_start(GTK_BOX(box), row, FALSE, FALSE, 10);
    return box;
}

static void hsv(double h, double s, double v, double *r, double *g, double *b) {
    double i = floor(h * 6.0);
    double f = h * 6.0 - i;
    double p = v * (1.0 - s);
    double q = v * (1.0 - f * s);
    double t = v * (1.0 - (1.0 - f) * s);
    switch ((int)i % 6) {
        case 0: *r = v; *g = t; *b = p; break;
        case 1: *r = q; *g = v; *b = p; break;
        case 2: *r = p; *g = v; *b = t; break;
        case 3: *r = p; *g = q; *b = v; break;
        case 4: *r = t; *g = p; *b = v; break;
        default: *r = v; *g = p; *b = q; break;
    }
}

static double phase_t = 0.0;

static void draw_bar(GtkWidget *w, cairo_t *cr, gpointer d) {
    (void)d;
    int width = gtk_widget_get_allocated_width(w);
    int height = gtk_widget_get_allocated_height(w);
    double radius = height / 2.0;

    cairo_set_source_rgba(cr, 1, 1, 1, 0.10);
    cairo_new_sub_path(cr);
    cairo_arc(cr, radius, height / 2.0, radius, M_PI / 2, 3 * M_PI / 2);
    cairo_arc(cr, width - radius, height / 2.0, radius, 3 * M_PI / 2, M_PI / 2);
    cairo_close_path(cr);
    cairo_fill(cr);

    double frac = (work_progress_pct >= 0) ? work_progress_pct / 100.0 : 0.3;
    if (frac < 0.06) frac = 0.06;
    double bar_w = width * frac;

    cairo_save(cr);
    cairo_new_sub_path(cr);
    cairo_arc(cr, radius, height / 2.0, radius, M_PI / 2, 3 * M_PI / 2);
    cairo_arc(cr, bar_w - radius, height / 2.0, radius, 3 * M_PI / 2, M_PI / 2);
    cairo_close_path(cr);
    cairo_clip(cr);

    cairo_pattern_t *g = cairo_pattern_create_linear(0, 0, bar_w > 40 ? bar_w : 40, 0);
    for (int i = 0; i <= 8; i++) {
        double t = i / 8.0;
        double hue = fmod(phase_t + t * 0.9, 1.0);
        double r, gg, b;
        hsv(hue, 0.6, 1.0, &r, &gg, &b);
        cairo_pattern_add_color_stop_rgb(g, t, r, gg, b);
    }
    cairo_set_source(cr, g);
    cairo_paint(cr);
    cairo_pattern_destroy(g);
    cairo_restore(cr);
}

static gboolean bar_tick(gpointer d) {
    (void)d;
    if (!A.progress || !gtk_widget_get_visible(A.progress)) return G_SOURCE_REMOVE;
    phase_t = fmod(phase_t + 0.012, 1.0);
    gtk_widget_queue_draw(A.progress);
    return G_SOURCE_CONTINUE;
}

static GtkWidget *pane_work(void) {
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 14);
    A.phase = gtk_label_new("Working");
    gtk_widget_set_halign(A.phase, GTK_ALIGN_START);
    gtk_style_context_add_class(gtk_widget_get_style_context(A.phase), "muted");
    gtk_box_pack_start(GTK_BOX(box), A.phase, FALSE, FALSE, 0);
    A.progress = gtk_drawing_area_new();
    gtk_widget_set_size_request(A.progress, -1, 6);
    g_signal_connect(A.progress, "draw", G_CALLBACK(draw_bar), NULL);
    gtk_box_pack_start(GTK_BOX(box), A.progress, FALSE, FALSE, 0);
    g_timeout_add(16, bar_tick, NULL);
    return box;
}

static GtkWidget *pane_result(void) {
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 12);
    GtkWidget *scroll = gtk_scrolled_window_new(NULL, NULL);
    gtk_widget_set_size_request(scroll, -1, 240);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll), GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);
    A.scroll = scroll;
    A.transcript = gtk_label_new("");
    gtk_label_set_line_wrap(GTK_LABEL(A.transcript), TRUE);
    gtk_label_set_selectable(GTK_LABEL(A.transcript), TRUE);
    gtk_label_set_xalign(GTK_LABEL(A.transcript), 0.0);
    gtk_label_set_yalign(GTK_LABEL(A.transcript), 0.0);
    gtk_widget_set_can_focus(A.transcript, FALSE);
    gtk_widget_set_hexpand(A.transcript, TRUE);

    gtk_widget_set_valign(A.transcript, GTK_ALIGN_START);
    gtk_container_add(GTK_CONTAINER(scroll), A.transcript);
    gtk_box_pack_start(GTK_BOX(box), scroll, TRUE, TRUE, 0);

    GtkWidget *row = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    A.copy_btn = gtk_button_new_with_label("Copy all");
    gtk_style_context_add_class(gtk_widget_get_style_context(A.copy_btn), "primary");
    g_signal_connect(A.copy_btn, "clicked", G_CALLBACK(on_copy), NULL);
    gtk_box_pack_start(GTK_BOX(row), A.copy_btn, FALSE, FALSE, 0);

    GtkWidget *more = gtk_button_new_with_label("Talk more");
    gtk_style_context_add_class(gtk_widget_get_style_context(more), "ghost");
    g_signal_connect(more, "clicked", G_CALLBACK(on_more), NULL);
    gtk_box_pack_start(GTK_BOX(row), more, FALSE, FALSE, 0);

    GtkWidget *file = gtk_button_new_with_label("Upload file");
    gtk_style_context_add_class(gtk_widget_get_style_context(file), "ghost");
    g_signal_connect(file, "clicked", G_CALLBACK(on_file), NULL);
    gtk_box_pack_start(GTK_BOX(row), file, FALSE, FALSE, 0);

    gtk_box_pack_start(GTK_BOX(box), row, FALSE, FALSE, 0);
    return box;
}

static GtkWidget *pane_error(void) {
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    A.error_label = gtk_label_new("Something went wrong.");
    gtk_label_set_line_wrap(GTK_LABEL(A.error_label), TRUE);
    gtk_label_set_xalign(GTK_LABEL(A.error_label), 0.0);
    gtk_box_pack_start(GTK_BOX(box), A.error_label, FALSE, FALSE, 0);
    GtkWidget *tip = gtk_label_new("Press Esc to dismiss.");
    gtk_style_context_add_class(gtk_widget_get_style_context(tip), "muted");
    gtk_widget_set_halign(tip, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(box), tip, FALSE, FALSE, 0);
    return box;
}

static gboolean on_map(GtkWidget *w, GdkEvent *e, gpointer d) {
    (void)w;
    (void)e;
    (void)d;
    fit_window();
    return FALSE;
}

static void build(void) {
    load_css();
    if (RENDER_MODE) {
        A.window = gtk_offscreen_window_new();
        gtk_widget_set_size_request(A.window, WIDTH, 340);
    } else {
        A.window = gtk_window_new(GTK_WINDOW_POPUP);
    }
    if (!RENDER_MODE) {
        gtk_window_set_keep_above(GTK_WINDOW(A.window), TRUE);
        gtk_window_set_skip_taskbar_hint(GTK_WINDOW(A.window), TRUE);
        gtk_window_set_skip_pager_hint(GTK_WINDOW(A.window), TRUE);
        gtk_window_set_resizable(GTK_WINDOW(A.window), FALSE);
        gtk_window_set_accept_focus(GTK_WINDOW(A.window), TRUE);
        gtk_window_set_focus_on_map(GTK_WINDOW(A.window), TRUE);
        gtk_window_stick(GTK_WINDOW(A.window));
    }
    gtk_window_set_default_size(GTK_WINDOW(A.window), WIDTH, 240);

    GdkScreen *screen = gtk_widget_get_screen(A.window);
    GdkVisual *visual = gdk_screen_get_rgba_visual(screen);
    if (visual) gtk_widget_set_visual(A.window, visual);
    gtk_widget_set_app_paintable(A.window, TRUE);
    g_signal_connect(A.window, "draw", G_CALLBACK(draw_background), NULL);
    g_signal_connect(A.window, "destroy", G_CALLBACK(gtk_main_quit), NULL);
    g_signal_connect(A.window, "key-press-event", G_CALLBACK(on_key), NULL);

    A.root = gtk_box_new(GTK_ORIENTATION_VERTICAL, 10);
    gtk_container_set_border_width(GTK_CONTAINER(A.root), 20);
    gtk_widget_set_margin_top(A.root, 4);
    gtk_widget_set_margin_bottom(A.root, 14);
    gtk_widget_set_size_request(A.root, WIDTH - 40, -1);
    gtk_container_add(GTK_CONTAINER(A.window), A.root);

    GtkWidget *head = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    A.title = gtk_label_new("Listening");
    gtk_style_context_add_class(gtk_widget_get_style_context(A.title), "title");
    gtk_widget_set_halign(A.title, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(head), A.title, TRUE, TRUE, 0);
    GtkWidget *close = gtk_button_new_with_label("✕");
    gtk_style_context_add_class(gtk_widget_get_style_context(close), "ghost");
    g_signal_connect(close, "clicked", G_CALLBACK(on_close), NULL);
    gtk_box_pack_end(GTK_BOX(head), close, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(A.root), head, FALSE, FALSE, 0);

    A.stack = gtk_stack_new();
    gtk_stack_set_homogeneous(GTK_STACK(A.stack), FALSE);
    gtk_stack_set_vhomogeneous(GTK_STACK(A.stack), FALSE);
    gtk_stack_set_transition_type(GTK_STACK(A.stack), GTK_STACK_TRANSITION_TYPE_CROSSFADE);
    gtk_stack_add_named(GTK_STACK(A.stack), pane_listen(), "listen");
    gtk_stack_add_named(GTK_STACK(A.stack), pane_work(), "work");
    gtk_stack_add_named(GTK_STACK(A.stack), pane_result(), "result");
    gtk_stack_add_named(GTK_STACK(A.stack), pane_error(), "error");
    gtk_box_pack_start(GTK_BOX(A.root), A.stack, TRUE, TRUE, 0);

    populate_mic();
    populate_lang();
    gtk_widget_show_all(A.window);
    if (!RENDER_MODE) {
        gtk_widget_hide(A.window);
        g_signal_connect(A.window, "map-event", G_CALLBACK(on_map), NULL);
        fit_window();
    }
}

static void render_png(const char *path) {
    for (int i = 0; i < 80; i++) while (gtk_events_pending()) gtk_main_iteration();

    GtkRequisition req;
    gtk_widget_get_preferred_size(A.root, &req, NULL);
    int w = WIDTH;
    int h = req.height + 24;

    GtkAllocation al;
    gtk_widget_get_allocation(A.root, &al);

    cairo_surface_t *surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, w, h);
    cairo_t *cr = cairo_create(surface);
    draw_notch(cr, w, h);
    cairo_translate(cr, al.x, al.y);
    gtk_widget_draw(A.root, cr);
    cairo_surface_write_to_png(surface, path);
    cairo_destroy(cr);
    cairo_surface_destroy(surface);
    fprintf(stderr, "[render] %s %dx%d (root at %d,%d)\n", path, w, h, al.x, al.y);
}

int main(int argc, char **argv) {
    g_setenv("GDK_BACKEND", "x11", TRUE);
    gtk_init(&argc, &argv);
    curl_global_init(CURL_GLOBAL_DEFAULT);
    CURL_H = curl_easy_init();
    read_token();
    if (argc > 1 && strcmp(argv[1], "--render") == 0) RENDER_MODE = 1;
    build();
    if (RENDER_MODE) {
        if (argc > 3) {
            GString *r = http_request("/state", NULL);
            apply_state(r->str);
            g_string_free(r, TRUE);
        }
        render_png(argv[2]);
        return 0;
    }
    g_timeout_add(16, on_tick, NULL);
    gtk_main();
    curl_easy_cleanup(CURL_H);
    curl_global_cleanup();
    return 0;
}
