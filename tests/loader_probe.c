/* SPDX-License-Identifier: GPL-3.0-or-later
 * Exercise the distribution's real embedded-Python loader and C menu-provider ABI.
 * The supplied FileInfo represents cached metadata, as Nautilus would provide it.
 */
#include <gmodule.h>
#include <nautilus-extension.h>

typedef struct { GTypeModule parent; } ProbeModule;
typedef struct { GTypeModuleClass parent; } ProbeModuleClass;
static const char *loader_path;
static void (*list_types)(const GType **, int *);
G_DEFINE_TYPE(ProbeModule, probe_module, G_TYPE_TYPE_MODULE)

static gboolean probe_load(GTypeModule *module) {
    GModule *library = g_module_open(loader_path, G_MODULE_BIND_LAZY);
    if (!library) g_error("Cannot open loader: %s", g_module_error());
    void (*initialize)(GTypeModule *);
    g_assert(g_module_symbol(library, "nautilus_module_initialize", (gpointer *)&initialize));
    g_assert(g_module_symbol(library, "nautilus_module_list_types", (gpointer *)&list_types));
    g_module_make_resident(library);
    initialize(module);
    return TRUE;
}
static void probe_unload(GTypeModule *module) { (void)module; }
static void probe_module_class_init(ProbeModuleClass *klass) {
    G_TYPE_MODULE_CLASS(klass)->load = probe_load;
    G_TYPE_MODULE_CLASS(klass)->unload = probe_unload;
}
static void probe_module_init(ProbeModule *self) { (void)self; }

typedef struct { GObject parent; } ProbeFile;
typedef struct { GObjectClass parent; } ProbeFileClass;
static const char *source_path;
static gboolean false_value(NautilusFileInfo *file) { (void)file; return FALSE; }
static GFileType file_type(NautilusFileInfo *file) { (void)file; return G_FILE_TYPE_REGULAR; }
static GFile *location(NautilusFileInfo *file) { (void)file; return g_file_new_for_path(source_path); }
static char *mime_type(NautilusFileInfo *file) { (void)file; return g_strdup("application/x-shellscript"); }
static void file_iface_init(NautilusFileInfoInterface *iface) {
    iface->is_gone = false_value;
    iface->is_directory = false_value;
    iface->get_file_type = file_type;
    iface->get_location = location;
    iface->get_mime_type = mime_type;
}
G_DEFINE_TYPE_WITH_CODE(ProbeFile, probe_file, G_TYPE_OBJECT,
                       G_IMPLEMENT_INTERFACE(NAUTILUS_TYPE_FILE_INFO, file_iface_init))
static void probe_file_class_init(ProbeFileClass *klass) { (void)klass; }
static void probe_file_init(ProbeFile *self) { (void)self; }

static void expect_file(const char *path, gboolean expected) {
    gint64 deadline = g_get_monotonic_time() + 10 * G_TIME_SPAN_SECOND;
    while (g_file_test(path, G_FILE_TEST_EXISTS) != expected) {
        while (g_main_context_pending(NULL)) g_main_context_iteration(NULL, FALSE);
        if (g_get_monotonic_time() > deadline) g_error("Helper did not update the launcher");
        g_usleep(10000);
    }
}

int main(int argc, char **argv) {
    g_assert(argc == 4 || argc == 5);
    loader_path = argv[1]; source_path = argv[2];
    GTypeModule *module = g_object_new(probe_module_get_type(), NULL);
    g_type_module_set_name(module, "add-to-applications-loader-probe");
    g_assert(g_type_module_use(module));
    const GType *types; int count;
    list_types(&types, &count);
    if (argc == 5) {
        g_assert_cmpstr(argv[4], ==, "--expect-uninstalled");
        g_assert_cmpint(count, ==, 0);
        g_print("Real embedded loader: extension is absent after uninstall\n");
        return 0;
    }
    g_assert_cmpint(count, ==, 1);
    g_assert(g_type_is_a(types[0], NAUTILUS_TYPE_MENU_PROVIDER));
    NautilusMenuProvider *provider = g_object_new(types[0], NULL);
    GObject *file = g_object_new(probe_file_get_type(), NULL);
    GList *files = g_list_append(NULL, file);
    GList *items = nautilus_menu_provider_get_file_items(provider, files);
    g_assert_cmpint(g_list_length(items), ==, 1);
    char *label;
    g_object_get(items->data, "label", &label, NULL);
    g_assert_cmpstr(label, ==, "Add to Applications");
    g_free(label);
    g_signal_emit_by_name(items->data, "activate");
    expect_file(argv[3], TRUE);
    g_list_free_full(items, g_object_unref);
    items = nautilus_menu_provider_get_file_items(provider, files);
    g_assert_cmpint(g_list_length(items), ==, 2);
    g_object_get(items->data, "label", &label, NULL);
    g_assert_cmpstr(label, ==, "Remove from Applications");
    g_free(label);
    g_signal_emit_by_name(items->data, "activate");
    expect_file(argv[3], FALSE);
    g_print("Real embedded loader: add and remove completed\n");
    return 0;
}
