// Los textos del aplicador en inglés. En el código van en español (T("...")); si la ventana está
// en inglés, T los busca acá. Los que faltan quedan en español.
using System.Collections.Generic;

static partial class Aplicador
{
    static int Idioma;  // 0 español, 1 inglés

    static string Titulo
    {
        get { return Edicion == "de" ? "Xenosaga Episode II Definitive Edition" : "Xenosaga Episode II en español"; }
    }

    static string T(string es, params object[] args)
    {
        string texto;
        if (Idioma == 0 || !Ingles.TryGetValue(es, out texto)) texto = es;
        return args.Length > 0 ? string.Format(texto, args) : texto;
    }

    static readonly Dictionary<string, string> Ingles = new Dictionary<string, string>
    {
        // núcleo (Aplicador.cs)
        { "no es una imagen ISO de DVD", "not a DVD ISO image" },
        { "el volumen {0} no tiene el formato esperado", "volume {0} does not have the expected format" },
        { "al programa le falta el paquete del parche", "the program is missing the patch package" },
        { "los datos de la Definitive Edition no son los esperados", "the Definitive Edition data is not what was expected" },
        { Anterior, "Disc {0}: it has an older version of the translation.\nApply the patch to your original ISO." },
        { "No es Xenosaga Episode II en versión americana (NTSC-U).", "This is not Xenosaga Episode II, US version (NTSC-U)." },
        { "Disco {0}: esta ISO ya tiene la traducción.", "Disc {0}: this ISO already has the translation." },
        { "Disco {0}: no es la versión original (¿otro parche?).", "Disc {0}: not the original version (another patch?)." },
        { "Disco {0}: listo para aplicar el parche.", "Disc {0}: ready to patch." },
        { "No se puede usar: {0}.", "Can't use it: {0}." },
        { "No se puede abrir: {0}", "Can't open it: {0}" },
        { "No se encuentra el archivo.", "File not found." },
        { "Disco {0}: comprobando los archivos...", "Disc {0}: checking files..." },
        { "el paquete está dañado ({0})", "the package is damaged ({0})" },
        { "Disco {0}: {1} archivos no son los originales. No se tocó nada.", "Disc {0}: {1} files are not the original ones. Nothing was changed." },
        { "... y {0} más", "... and {0} more" },
        { "¿Es otra versión o una ISO con otro parche?", "Is it another version, or an ISO with another patch?" },
        { " (Español + Definitive)", " (Spanish + Definitive)" },
        { " (Español)", " (Spanish)" },
        { "Ya existe \"{0}\". ¿Reemplazarlo?", "\"{0}\" already exists. Replace it?" },
        { "No se tocó nada.", "Nothing was changed." },
        { "Falta espacio: hacen falta {0} GB libres en {1}.", "Not enough space: {0} GB free are needed on {1}." },
        { "Disco {0}: creando \"{1}\"...", "Disc {0}: creating \"{1}\"..." },
        { "Disco {0}: verificando...", "Disc {0}: verifying..." },
        { "la ISO creada no coincide con la esperada", "the new ISO does not match the expected one" },
        { "Error: {0}", "Error: {0}" },
        { "Listo: disco {0} con la Definitive Edition.", "Done: disc {0} with the Definitive Edition." },
        { "Listo: disco {0} traducido y con la Definitive Edition.", "Done: disc {0} translated and with the Definitive Edition." },
        { "Listo: disco {0} traducido ({1} archivos).", "Done: disc {0} translated ({1} files)." },
        { " (s/n): ", " (y/n): " },
        { "s", "y" },
        { "Xenosaga Episode II en español", "Xenosaga Episode II in Spanish" },
        { "versión {0}", "version {0}" },
        { "este paquete no trae la Definitive Edition", "this package does not include the Definitive Edition" },
        { "perfil desconocido: {0}", "unknown profile: {0}" },
        { "opción desconocida: {0}", "unknown option: {0}" },
        { "Error inesperado: {0}", "Unexpected error: {0}" },
        { "Terminado.", "Finished." },
        { "Terminado con problemas.", "Finished with problems." },

        // ventana (Ventana.cs)
        { "al programa le falta el arte", "the program is missing its artwork" },
        { "Arrastra las ISO a la ventana o haz clic en cada disco.", "Drag the ISOs onto the window or click each disc." },
        { "Se crean copias nuevas: tus ISO no se modifican.", "New copies are created: your ISOs are not modified." },
        { "Arrastra la ISO o haz clic", "Drag the ISO or click" },
        { "ESPAÑOL", "SPANISH" },
        { "PERSONALIZADA", "CUSTOM" },
        { "TRABAJANDO...", "WORKING..." },
        { "ELIGE QUÉ APLICAR", "CHOOSE WHAT TO APPLY" },
        { "ELIGE UNA ISO", "CHOOSE AN ISO" },
        { "1 DISCO", "1 DISC" },
        { "{0} DISCOS", "{0} DISCS" },
        { "DEFINITIVE EDITION  //  CONFIGURACIÓN", "DEFINITIVE EDITION  //  SETTINGS" },
        { "PERFIL", "PROFILE" },
        { "DETALLE", "DETAILS" },
        { "EN PRUEBA", "TESTING" },
        { "Todavía no se probó en el juego.", "Not tested in the game yet." },
        { "PERFIL {0}", "PROFILE: {0}" },
        { "PERFIL PERSONALIZADO", "CUSTOM PROFILE" },
        { "Partiendo de {0}, con tus cambios.", "Based on {0}, with your changes." },
        { "> Clic en una casilla para activarla.  Clic en ‹ › para cambiar cuánto.", "> Click a box to turn it on.  Click ‹ › to change how much." },
        { "Elige la ISO del disco {0}", "Choose the ISO for disc {0}" },
        { "Imágenes ISO (*.iso)|*.iso|Todos los archivos (*.*)|*.*", "ISO images (*.iso)|*.iso|All files (*.*)|*.*" },
        { "Marca la traducción, la Definitive Edition o las dos.", "Check the translation, the Definitive Edition or both." },
        { "No hay ninguna ISO original para parchear.", "There is no original ISO to patch." },
        { "Primero elige al menos una ISO.", "First choose at least one ISO." },
        { "Cancelado.", "Cancelled." },
        { "Terminado: ya puedes jugar con las ISO nuevas.", "Done: you can now play with the new ISOs." },
        { "En este equipo no se puede reproducir la música.", "Music can't be played on this computer." },
        { "No está el LEEME.txt junto al programa.", "README.txt is not next to the program." },
        { "No se pudo abrir el LEEME.txt.", "Could not open README.txt." },
        { "Se está creando una ISO. ¿Cancelar y salir? Lo que se creó hasta ahora se borra.", "An ISO is being created. Cancel and exit? What was created so far will be deleted." },
        { "Cancelando...", "Cancelling..." },
        { "CONFIRMAR", "CONFIRM" },
    };
}
