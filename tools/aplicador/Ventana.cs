// La ventana del aplicador, con estética de keygen de los 2000 y de Xenosaga Episode II.
//
// El arte, los sonidos y la música vienen de arte.zip y las medidas, de Diseno.cs; los dos los arma
// tools/aplicador/arte.py. El fondo está en dos capas para que el brillo de la gema del Zohar
// lata entre ellas; lo demás (casillas, ranuras, botón, progreso, registro, créditos) se dibuja
// encima. El engranaje de la Definitive Edition abre su configuración sobre la misma ventana.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Drawing.Text;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

static partial class Aplicador
{
    // Imágenes y sonidos de arte.zip.
    class Arte
    {
        public readonly Dictionary<string, Bitmap> Img = new Dictionary<string, Bitmap>();
        public readonly Dictionary<string, byte[]> Datos = new Dictionary<string, byte[]>();

        public Arte()
        {
            Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream("arte.zip");
            if (s == null) throw new InvalidDataException(T("al programa le falta el arte"));
            using (var zip = new ZipArchive(s, ZipArchiveMode.Read))
                foreach (ZipArchiveEntry e in zip.Entries)
                {
                    byte[] data = ReadEntry(zip, e.FullName);
                    if (!e.FullName.EndsWith(".png"))
                        Datos[e.FullName] = data;
                    else
                        using (var m = new MemoryStream(data))
                        using (var src = new Bitmap(m))
                            Img[e.FullName.Substring(0, e.FullName.Length - 4)] = Rapida(src);
                }
        }

        // Copia en el formato que GDI+ dibuja más rápido.
        static Bitmap Rapida(Image src)
        {
            var b = new Bitmap(src.Width, src.Height, PixelFormat.Format32bppPArgb);
            using (Graphics g = Graphics.FromImage(b)) g.DrawImage(src, 0, 0, src.Width, src.Height);
            return b;
        }

        // Las imágenes con texto vienen en los dos idiomas: "boton_es_normal", "boton_en_normal"...
        public Bitmap Rotulo(string nombre, string estado)
        {
            return Img[nombre + "_" + Sigla + (estado != null ? "_" + estado : "")];
        }
    }

    static string Sigla { get { return Idioma == 0 ? "es" : "en"; } }

    // De medidas de diseño (las de arte.py y Diseno.cs) a píxeles de la ventana.
    static int Px(float v) { return (int)Math.Round(v * Diseno.Escala); }
    static Rectangle Px(Rectangle r) { return Rectangle.FromLTRB(Px(r.Left), Px(r.Top), Px(r.Right), Px(r.Bottom)); }

    // Una imagen en su tamaño real, en una posición de diseño.
    static void Dibujar(Graphics g, Bitmap b, float x, float y)
    {
        g.DrawImage(b, new Rectangle(Px(x), Px(y), b.Width, b.Height), 0, 0, b.Width, b.Height, GraphicsUnit.Pixel);
    }

    // Un texto guardado como imagen (arte.suelto), para que empiece en (x, y).
    static void DibujarTexto(Graphics g, Bitmap b, float x, float y) { Dibujar(g, b, x - Diseno.Margen, y - Diseno.Margen); }

    static void DibujarTransparente(Graphics g, Bitmap b, float x, float y, float alfa)
    {
        using (var attrs = new ImageAttributes())
        {
            attrs.SetColorMatrix(new ColorMatrix { Matrix33 = Math.Max(0f, Math.Min(1f, alfa)) });
            g.DrawImage(b, new Rectangle(Px(x), Px(y), b.Width, b.Height), 0, 0, b.Width, b.Height, GraphicsUnit.Pixel, attrs);
        }
    }

    // Una letra de Windows, o la de reemplazo si falta (Bahnschrift viene desde Windows 10).
    static Font Letra(string familia, float tamano, string reemplazo = "Segoe UI", FontStyle estilo = FontStyle.Regular)
    {
        var f = new Font(familia, tamano, estilo, GraphicsUnit.Pixel);
        if (f.Name == familia) return f;
        f.Dispose();
        return new Font(reemplazo, tamano, estilo, GraphicsUnit.Pixel);
    }

    // Efectos de sonido (WAV en memoria; PlaySound los lee de ahí mientras suenan).
    class Sonidos
    {
        [DllImport("winmm.dll")]
        static extern bool PlaySound(IntPtr sound, IntPtr module, uint flags);
        const uint SND_ASYNC = 0x1, SND_NODEFAULT = 0x2, SND_MEMORY = 0x4;
        readonly Dictionary<string, IntPtr> memoria = new Dictionary<string, IntPtr>();

        public Sonidos(Arte arte)
        {
            foreach (var kv in arte.Datos.Where(kv => kv.Key.StartsWith("sfx_")))
            {
                IntPtr p = Marshal.AllocHGlobal(kv.Value.Length);
                Marshal.Copy(kv.Value, 0, p, kv.Value.Length);
                memoria[kv.Key.Substring(4, kv.Key.Length - 8)] = p;
            }
        }

        public void Tocar(string nombre)
        {
            IntPtr p;
            if (memoria.TryGetValue(nombre, out p)) PlaySound(p, IntPtr.Zero, SND_ASYNC | SND_NODEFAULT | SND_MEMORY);
        }
    }

    // El tema de fondo, con MCI (viene con Windows y lee MP3). Se copia a la carpeta temporal porque
    // MCI necesita un archivo.
    class Musica
    {
        [DllImport("winmm.dll", CharSet = CharSet.Unicode)]
        static extern int mciSendString(string command, StringBuilder buffer, int size, IntPtr callback);
        public const int MM_MCINOTIFY = 0x3B9, MCI_NOTIFY_SUCCESSFUL = 1;
        static readonly int[] Volumen = { 0, 15, 30, 50, 80, 120 };  // escala de MCI (0 a 1000), niveles 0 a 5
        public readonly bool Disponible;
        readonly IntPtr ventana;
        bool sonando;

        public Musica(byte[] mp3, IntPtr ventana)
        {
            this.ventana = ventana;
            if (mp3 == null) return;
            string path = Path.Combine(Path.GetTempPath(), "xenosaga2_es_tema.mp3");
            try
            {
                if (!File.Exists(path) || new FileInfo(path).Length != mp3.Length) File.WriteAllBytes(path, mp3);
            }
            catch (IOException) { return; }
            catch (UnauthorizedAccessException) { return; }
            Disponible = Mci("open \"" + path + "\" type mpegvideo alias tema");
        }

        bool Mci(string command, bool notify = false)
        {
            return mciSendString(command, null, 0, notify ? ventana : IntPtr.Zero) == 0;
        }

        public void Nivel(int nivel)
        {
            if (!Disponible) return;
            if (nivel == 0)
            {
                Mci("pause tema");
                sonando = false;
                return;
            }
            Mci("setaudio tema volume to " + Volumen[nivel]);
            if (!sonando) Mci("play tema notify", true);
            sonando = true;
        }

        // MCI avisa a la ventana cuando el tema termina: vuelve a empezar.
        public void Termino()
        {
            if (!sonando) return;
            Mci("seek tema to start");
            Mci("play tema notify", true);
        }

        public void Cerrar()
        {
            if (Disponible) Mci("close tema");
        }
    }

    class Ranura
    {
        public string Ruta;
        public string Estado;  // el chip: original, traducida, anterior, distinta, novalida, encurso, lista o error
    }

    // Lo que cuenta Process desde el hilo de trabajo, pasado a la ventana.
    class AvisoVentana : IAviso
    {
        readonly Ventana ventana;
        readonly int indice, total;
        int ultimo = -1;

        public AvisoVentana(Ventana ventana, int indice, int total)
        {
            this.ventana = ventana;
            this.indice = indice;
            this.total = total;
        }

        public void Linea(string texto) { ventana.EnLaVentana(() => ventana.Registrar(texto)); }

        public void Detalle(string texto) { }  // en la ventana alcanza con el resumen

        public void Avance(int porcentaje)
        {
            if (ventana.Cancelar) throw new OperationCanceledException();
            int general = (indice * 100 + porcentaje) / total;
            if (general == ultimo) return;
            ultimo = general;
            ventana.EnLaVentana(() => ventana.Avance(general));
        }

        public bool Confirmar(string pregunta)
        {
            return (bool)ventana.Invoke(new Func<bool>(() => Dialogo.Preguntar(ventana, pregunta)));
        }
    }

    class Ventana : Form
    {
        enum Zona
        {
            Nada, Minimizar, Cerrar, Idioma, Ranura1, Ranura2, Boton, Musica, Leeme, Salir,
            Traduccion, Definitiva, Engranaje,                            // las casillas de arriba
            Perfil, Opcion, NivelMenos, NivelMas, Restablecer, Listo,     // la configuración (con un índice)
        }

        [DllImport("user32.dll")]
        static extern bool ReleaseCapture();
        [DllImport("user32.dll")]
        static extern IntPtr SendMessage(IntPtr hWnd, int msg, IntPtr wParam, IntPtr lParam);

        static readonly Color Cian = Color.FromArgb(90, 220, 255), Violeta = Color.FromArgb(170, 120, 255), Ambar = Color.FromArgb(255, 190, 90);
        const string Glifos = "ÄÖÜßABCDEGHJKLMNRSTUVXZ#%&$@0123456789";
        internal readonly Arte Arte;
        internal readonly Sonidos Sonidos;
        internal volatile bool Cancelar;
        readonly Bitmap fondo;  // las dos capas juntas, sin el brillo de la gema
        readonly Rectangle zonaGema, zonaFrase;
        readonly Dictionary<string, List<PatchEntry>> manifest;
        readonly Definitiva de;  // null si el paquete no la trae
        readonly Ranura[] ranuras = { new Ranura(), new Ranura() };
        readonly List<string> registro = new List<string>();
        readonly System.Diagnostics.Stopwatch reloj = System.Diagnostics.Stopwatch.StartNew();
        readonly System.Windows.Forms.Timer animacion = new System.Windows.Forms.Timer { Interval = 33 };
        readonly Font mono = new Font("Consolas", 10f, GraphicsUnit.Pixel);
        readonly Font monoChica = new Font("Consolas", 9f, GraphicsUnit.Pixel);
        readonly Font monoGrande = new Font("Consolas", 11f, FontStyle.Bold, GraphicsUnit.Pixel);
        readonly Font fTitulo = Letra("Bahnschrift SemiCondensed", 12f);
        readonly Font fNegrita = Letra("Bahnschrift SemiBold SemiConden", 11f, "Segoe UI Semibold");
        readonly Font fGrupo = Letra("Bahnschrift SemiBold SemiConden", 9.5f, "Segoe UI Semibold");
        readonly Font fOpcion = Letra("Bahnschrift SemiCondensed", 10.5f);
        readonly Font fChip = Letra("Bahnschrift SemiBold SemiConden", 7.5f, "Segoe UI Semibold");
        readonly Font fNivel = Letra("Segoe UI Semibold", 9.5f);
        readonly Font fDetalleTitulo = Letra("Bahnschrift SemiBold SemiConden", 12f, "Segoe UI Semibold");
        readonly Font fDetalle = Letra("Segoe UI", 9.5f);
        readonly Font fPerfil = Letra("Segoe UI", 8.5f);
        readonly Font fSimbolo = Letra("Segoe UI Symbol", 9f);
        readonly StringFormat recortado = new StringFormat(StringFormat.GenericTypographic)
        {
            Trimming = StringTrimming.EllipsisCharacter,
            FormatFlags = StringFormatFlags.NoWrap,
        };
        readonly float[] umbrales;  // en qué punto del avance se descifra cada letra de la frase
        Musica musica;
        Zona sobre, apretada;
        int sobreIndice = -1, apretadaIndice = -1, nivel = 2, progreso;
        bool trabajando, cerrarAlTerminar, registroInicial;
        double tiempo;  // en segundos, para las animaciones
        double revelada = -1;  // cuándo terminó de aplicarse la traducción (la frase queda en español)

        // Qué se va a aplicar.
        bool traduccion, definitiva;
        readonly Dictionary<string, int> niveles = new Dictionary<string, int>();
        readonly Dictionary<string, int> recordados = new Dictionary<string, int>();  // el último nivel de cada opción
        string perfilBase = "definitiva";
        bool configAbierta;
        OpcionDe foco;
        Seleccion enCurso;

        // La configuración: dónde va cada fila (en medidas de diseño).
        static readonly Rectangle Panel = Rectangle.FromLTRB(16, 32, 744, 381);
        static readonly Rectangle Lista = Rectangle.FromLTRB(24, 94, 470, 350), Detalle = Rectangle.FromLTRB(482, 94, 736, 350);
        const int PerfilX = 80, PerfilY = 62, PerfilAncho = 104, PerfilAlto = 22, PerfilPaso = 110;
        readonly List<int> filas = new List<int>();  // y de cada opción
        readonly List<KeyValuePair<string, int>> encabezados = new List<KeyValuePair<string, int>>();

        public Ventana(IEnumerable<string> isos)
        {
            Arte = new Arte();
            Sonidos = new Sonidos(Arte);
            using (ZipArchive zip = OpenPackage(out manifest)) de = LeerDefinitiva(zip);
            fondo = new Bitmap(Px(Diseno.Ancho), Px(Diseno.Alto), PixelFormat.Format32bppPArgb);
            using (Graphics g = Graphics.FromImage(fondo))
            {
                Dibujar(g, Arte.Img["fondo_atras"], 0, 0);
                Dibujar(g, Arte.Img["fondo_frente"], 0, 0);
            }
            Bitmap gema = Arte.Img["gema"];
            zonaGema = new Rectangle(Px(Diseno.Gema.X) - gema.Width / 2, Px(Diseno.Gema.Y) - gema.Height / 2, gema.Width, gema.Height);
            zonaFrase = Px(new Rectangle(0, (int)Diseno.FraseY - Diseno.Margen, Diseno.Ancho, 30));
            var azar = new Random(7);
            umbrales = Diseno.FraseEs.Select(c => (float)(azar.NextDouble() * 0.9)).ToArray();

            traduccion = Edicion == "es";
            definitiva = Edicion == "de" && de != null;
            if (de != null)
            {
                ElegirPerfil("definitiva");
                foco = de.Opciones[0];
                int y = 100;
                string grupo = null;
                foreach (OpcionDe o in de.Opciones)
                {
                    if (o.Grupo != grupo)
                    {
                        grupo = o.Grupo;
                        if (y > 100) y += 3;
                        encabezados.Add(new KeyValuePair<string, int>(grupo, y));
                        y += 15;
                    }
                    filas.Add(y);
                    y += 16;
                }
            }

            Text = T(Titulo);
            FormBorderStyle = FormBorderStyle.None;
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = fondo.Size;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.Opaque, true);
            AllowDrop = true;
            KeyPreview = true;
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); }
            catch (ArgumentException) { }
            animacion.Tick += (s, e) => Animar();

            Bienvenida();
            foreach (string iso in isos) Asignar(iso, -1, false);
        }

        void Bienvenida()
        {
            registro.Clear();
            Registrar(T("Arrastra las ISO a la ventana o haz clic en cada disco."));
            Registrar(T("Se crean copias nuevas: tus ISO no se modifican."));
            registroInicial = true;
        }

        protected override CreateParams CreateParams
        {
            get
            {
                CreateParams cp = base.CreateParams;
                cp.Style |= 0x20000;       // WS_MINIMIZEBOX: minimizar y restaurar desde la barra de tareas
                cp.ClassStyle |= 0x20000;  // CS_DROPSHADOW
                return cp;
            }
        }

        protected override void OnShown(EventArgs e)
        {
            base.OnShown(e);
            byte[] mp3;
            Arte.Datos.TryGetValue("tema.mp3", out mp3);
            musica = new Musica(mp3, Handle);
            if (!musica.Disponible) nivel = 0;
            musica.Nivel(nivel);
            animacion.Start();
        }

        protected override void WndProc(ref Message m)
        {
            if (m.Msg == Musica.MM_MCINOTIFY && (int)m.WParam == Musica.MCI_NOTIFY_SUCCESSFUL && musica != null) musica.Termino();
            base.WndProc(ref m);
        }

        internal void EnLaVentana(Action accion)
        {
            if (IsHandleCreated && !IsDisposed) BeginInvoke(accion);
        }

        internal void Registrar(string texto)
        {
            registroInicial = false;
            registro.Add(texto);
            if (registro.Count > 20) registro.RemoveAt(0);
            Invalidate(Px(Diseno.Registro));
        }

        internal void Avance(int porcentaje)
        {
            if (porcentaje == progreso) return;
            progreso = porcentaje;
            Rectangle p = Diseno.Progreso;
            Invalidate(Px(new Rectangle(p.X, p.Y - 4, p.Width + 50, p.Height + 8)));
        }

        void Animar()
        {
            tiempo = reloj.Elapsed.TotalSeconds;
            Invalidate(zonaGema);
            Invalidate(Px(Diseno.Scroller));
            if (configAbierta) return;
            Invalidate(zonaFrase);
            Invalidate(Px(Diseno.BotonZona));
            Invalidate(Px(Diseno.Registro));
        }

        // ---- Selección ----

        int NivelDe(string id)
        {
            int n;
            return niveles.TryGetValue(id, out n) ? n : 0;
        }

        void ElegirPerfil(string id)
        {
            PerfilDe p = de.Perfil(id);
            perfilBase = id;
            foreach (OpcionDe o in de.Opciones)
            {
                int n;
                niveles[o.Id] = p.Niveles.TryGetValue(o.Id, out n) ? n : 0;
                if (n > 0) recordados[o.Id] = n;
            }
        }

        // El perfil que coincide con la selección, o null si es personalizada.
        PerfilDe PerfilActual()
        {
            return de.Perfiles.FirstOrDefault(p => de.Opciones.All(o =>
            {
                int n;
                return NivelDe(o.Id) == (p.Niveles.TryGetValue(o.Id, out n) ? n : 0);
            }));
        }

        bool ConDefinitiva { get { return de != null && definitiva && niveles.Values.Any(n => n > 0); } }

        Seleccion SeleccionActual()
        {
            var sel = new Seleccion { Traduccion = traduccion };
            if (ConDefinitiva)
                foreach (var kv in niveles) sel.Niveles[kv.Key] = kv.Value;
            return sel;
        }

        // Lo que dice el botón: "ESPAÑOL + DEFINITIVA", "DEFINITIVA", "ESPAÑOL"...
        string Etiqueta()
        {
            var partes = new List<string>();
            if (traduccion) partes.Add(T("ESPAÑOL"));
            if (ConDefinitiva)
            {
                PerfilDe p = PerfilActual();
                partes.Add(p != null ? p.Nombre[Idioma].ToUpper() : T("PERSONALIZADA"));
            }
            return string.Join(" + ", partes);
        }

        bool Aplicable(Ranura r)
        {
            return r.Estado == "original" || (r.Estado == "traducida" && ConDefinitiva);
        }

        int Pendientes { get { return traduccion || ConDefinitiva ? ranuras.Count(Aplicable) : 0; } }

        // ---- Dibujo ----

        protected override void OnPaint(PaintEventArgs e) { Pintar(e.Graphics, e.ClipRectangle); }

        // Por capas: imágenes en píxeles de la ventana; textos y formas, en medidas de diseño con la
        // escala aplicada (así quedan nítidos); encima, los textos guardados como imagen.
        void Pintar(Graphics g, Rectangle clip)
        {
            g.InterpolationMode = InterpolationMode.NearestNeighbor;
            g.PixelOffsetMode = PixelOffsetMode.Half;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
            g.DrawImage(fondo, clip, clip, GraphicsUnit.Pixel);
            if (clip.IntersectsWith(zonaGema)) PintarGema(g);
            if (clip.IntersectsWith(Px(Diseno.Scroller))) PintarScroller(g);
            DibujarTexto(g, Arte.Rotulo("titulo", null), 12, 6);
            DibujarTexto(g, Arte.Rotulo("pie", null), 86, 424);
            for (int i = 0; i < 2; i++)
            {
                Rectangle r = Diseno.Ranuras[i];
                DibujarTexto(g, Arte.Rotulo("disco" + (i + 1), null), r.X + 12, r.Y + 3);
                if (ranuras[i].Ruta != null) Dibujar(g, Arte.Rotulo("chip", ranuras[i].Estado), r.Right - 78, r.Y + 8);
            }
            Dibujar(g, Arte.Rotulo("boton", EstadoBoton), Diseno.BotonZona.X, Diseno.BotonZona.Y);
            PintarBotonChico(g, Arte.Rotulo("musica", Estado(Zona.Musica)), Diseno.Musica);
            PintarBotonChico(g, Arte.Rotulo("leeme", Estado(Zona.Leeme)), Diseno.Leeme);
            PintarBotonChico(g, Arte.Rotulo("salir", Estado(Zona.Salir)), Diseno.Salir);
            PintarBotonChico(g, Arte.Img["minimizar_" + Estado(Zona.Minimizar)], Diseno.Minimizar);
            PintarBotonChico(g, Arte.Img["cerrar_" + Estado(Zona.Cerrar)], Diseno.Cerrar);
            PintarFrase(g);

            GraphicsState estado = g.Save();
            g.ScaleTransform(Diseno.Escala, Diseno.Escala);
            for (int i = 0; i < 2; i++) PintarRanura(g, i);
            PintarBoton(g);
            PintarProgreso(g);
            PintarRegistro(g);
            PintarFraseCifrada(g);
            for (int k = 0; k < 5; k++)
            {
                int h = 4 + k * 2;
                bool activa = musica != null && musica.Disponible && k < nivel;
                using (var b = new SolidBrush(activa ? Color.FromArgb(14, 16, 26) : Color.FromArgb(150, 70, 76, 96)))
                    g.FillRectangle(b, Diseno.Musica.X + 54 + k * 5, Diseno.Musica.Bottom - 6 - h, 3, h);
            }
            PintarModulos(g);
            PintarIdiomas(g);
            g.Restore(estado);
            PintarModulosTexto(g);

            if (!configAbierta) return;
            estado = g.Save();
            g.ScaleTransform(Diseno.Escala, Diseno.Escala);
            PintarConfig(g);
            g.Restore(estado);
            PintarBotonChico(g, Arte.Rotulo("restablecer", Estado(Zona.Restablecer)), Diseno.Restablecer);
            PintarBotonChico(g, Arte.Rotulo("listo", Estado(Zona.Listo)), Diseno.Listo);
        }

        string Estado(Zona zona)
        {
            return apretada == zona && sobre == zona ? "presionado" : sobre == zona ? "hover" : "normal";
        }

        void PintarBotonChico(Graphics g, Bitmap b, Rectangle r) { Dibujar(g, b, r.X, r.Y); }

        void PintarGema(Graphics g)
        {
            Rectangle z = zonaGema;
            g.DrawImage(Arte.Img["fondo_atras"], z, z, GraphicsUnit.Pixel);
            using (var attrs = new ImageAttributes())
            {
                attrs.SetColorMatrix(new ColorMatrix { Matrix33 = (float)(0.55 + 0.45 * Math.Sin(tiempo * 2.4)) });
                g.DrawImage(Arte.Img["gema"], z, 0, 0, z.Width, z.Height, GraphicsUnit.Pixel, attrs);
            }
            g.DrawImage(Arte.Img["fondo_frente"], z, z, GraphicsUnit.Pixel);
        }

        static Point[] Chaflan(Rectangle r, int corte)
        {
            return new[]
            {
                new Point(r.X, r.Y), new Point(r.Right - corte, r.Y), new Point(r.Right, r.Y + corte),
                new Point(r.Right, r.Bottom), new Point(r.X + corte, r.Bottom), new Point(r.X, r.Bottom - corte),
            };
        }

        static void Caja(Graphics g, Rectangle r, int corte, Color relleno, Color borde)
        {
            Point[] forma = Chaflan(r, corte);
            using (var b = new SolidBrush(relleno)) g.FillPolygon(b, forma);
            using (var p = new Pen(borde)) g.DrawPolygon(p, forma);
        }

        static void Casilla(Graphics g, float x, float y, bool on, float lado)
        {
            using (var fondoCasilla = new SolidBrush(Color.FromArgb(4, 8, 22))) g.FillRectangle(fondoCasilla, x, y, lado, lado);
            using (var p = new Pen(Color.FromArgb(on ? 255 : 110, Cian))) g.DrawRectangle(p, x, y, lado, lado);
            if (on)
                using (var b = new SolidBrush(Cian)) g.FillRectangle(b, x + 2, y + 2, lado - 4, lado - 4);
        }

        // ---- La frase: "Jenseits von Gut und Böse" que se descifra al español ----

        enum EstadoFrase { Aleman, Cifrada, Espanol }

        EstadoFrase Frase
        {
            get
            {
                if (trabajando && enCurso != null && enCurso.Traduccion) return EstadoFrase.Cifrada;
                return revelada >= 0 && traduccion ? EstadoFrase.Espanol : EstadoFrase.Aleman;
            }
        }

        float Avance01 { get { return progreso / 100f; } }

        void PintarFrase(Graphics g)
        {
            float y = Diseno.FraseY - Diseno.Margen;
            switch (Frase)
            {
                case EstadoFrase.Aleman:
                    Dibujar(g, Arte.Img["frase_de"], 0, y);
                    break;
                case EstadoFrase.Espanol:
                    // destello al terminar y después late con la gema
                    double desde = tiempo - revelada;
                    float destello = (float)Math.Max(0, 1 - desde / 1.4);
                    float pulso = (float)(0.72 + 0.28 * Math.Sin(tiempo * 2.4));
                    DibujarTransparente(g, Arte.Img["frase_es_brillo"], 0, y, pulso + destello);
                    if (destello > 0) DibujarTransparente(g, Arte.Img["frase_es_brillo"], 0, y, destello);
                    Dibujar(g, Arte.Img["frase_es"], 0, y);
                    break;
                case EstadoFrase.Cifrada:
                    for (int i = 0; i < umbrales.Length; i++)
                    {
                        if (Diseno.FraseEs[i] == ' ' || Avance01 < umbrales[i]) continue;
                        GraphicsState s = g.Save();
                        g.SetClip(Px(Rectangle.FromLTRB((int)Diseno.FraseX[i] - 2, (int)y, (int)(Diseno.FraseX[i] + Diseno.FraseAncho[i]) + 3, (int)y + 30)),
                                  CombineMode.Intersect);
                        Dibujar(g, Arte.Img["frase_es_halo"], 0, y);
                        Dibujar(g, Arte.Img["frase_es"], 0, y);
                        g.Restore(s);
                    }
                    break;
            }
        }

        // Las letras que todavía no se descifraron: símbolos que cambian solos.
        void PintarFraseCifrada(Graphics g)
        {
            if (Frase != EstadoFrase.Cifrada) return;
            int paso = (int)(tiempo * 14);
            using (var b = new SolidBrush(Color.FromArgb(150, Cian)))
                for (int i = 0; i < umbrales.Length; i++)
                {
                    if (Diseno.FraseEs[i] == ' ' || Avance01 >= umbrales[i]) continue;
                    string glifo = Glifos[(i * 7 + paso * 13 + i * paso) % Glifos.Length].ToString();
                    SizeF m = g.MeasureString(glifo, mono, PointF.Empty, StringFormat.GenericTypographic);
                    g.DrawString(glifo, mono, b, Diseno.FraseX[i] + (Diseno.FraseAncho[i] - m.Width) / 2, Diseno.FraseY + 1, StringFormat.GenericTypographic);
                }
        }

        // ---- Casillas de arriba y selector de idioma ----

        Rectangle EngranajeZona { get { Rectangle r = Diseno.ModuloDe; return Rectangle.FromLTRB(r.Right - 26, r.Y + 4, r.Right - 5, r.Bottom - 4); } }

        void PintarModulos(Graphics g)
        {
            PintarModulo(g, Diseno.ModuloTraduccion, traduccion, Zona.Traduccion);
            if (de == null) return;
            PintarModulo(g, Diseno.ModuloDe, definitiva, Zona.Definitiva);
            bool encima = sobre == Zona.Engranaje && !trabajando && !configAbierta;
            Caja(g, EngranajeZona, 4, encima ? Color.FromArgb(40, 90, 160) : Color.FromArgb(20, 40, 90), Color.FromArgb(encima ? 255 : 220, Cian));
        }

        void PintarModulo(Graphics g, Rectangle r, bool on, Zona zona)
        {
            bool encima = sobre == zona && !trabajando && !configAbierta;
            Caja(g, r, 7, Color.FromArgb(225, 8, 14, 38), encima ? Color.FromArgb(200, 255, 255, 255) : Color.FromArgb(on ? 190 : 70, Cian));
            Casilla(g, r.X + 8, r.Y + 7, on, 10);
        }

        void PintarModulosTexto(Graphics g)
        {
            for (int k = 0; k < 2; k++)
            {
                Rectangle b = Diseno.Idiomas[k];
                string on = Idioma == k ? "on" : "off";
                Dibujar(g, Arte.Img["bandera_" + (k == 0 ? "ar" : "us") + "_" + on], b.X + 4, 7);
                DibujarTexto(g, Arte.Img["idioma_" + (k == 0 ? "es" : "en") + "_" + on], b.X + 23, 5.5f);
            }
            Rectangle r = Diseno.ModuloTraduccion;
            DibujarTexto(g, Arte.Rotulo("mod_traduccion", traduccion ? "on" : "off"), r.X + 25, r.Y + 4.5f);
            if (de == null) return;
            r = Diseno.ModuloDe;
            DibujarTexto(g, Arte.Img[definitiva ? "mod_de_on" : "mod_de_off"], r.X + 25, r.Y + 4.5f);
            DibujarTexto(g, Arte.Img["engranaje"], EngranajeZona.X + 5, r.Y + 4);
        }

        void PintarIdiomas(Graphics g)
        {
            for (int k = 0; k < 2; k++)
            {
                bool on = Idioma == k, encima = sobre == Zona.Idioma && sobreIndice == k;
                Caja(g, Diseno.Idiomas[k], 3, on ? Color.FromArgb(24, 90, 150) : Color.FromArgb(10, 16, 36),
                     encima ? Color.White : on ? Cian : Color.FromArgb(70, 80, 110));
            }
        }

        // ---- Ranuras, botón, progreso y registro ----

        void PintarRanura(Graphics g, int i)
        {
            Rectangle r = Diseno.Ranuras[i];
            Ranura ranura = ranuras[i];
            bool llena = ranura.Ruta != null, encima = sobre == (i == 0 ? Zona.Ranura1 : Zona.Ranura2) && !trabajando;
            if (llena || encima)
                using (var pen = new Pen(encima ? Color.FromArgb(200, 255, 255, 255) : Color.FromArgb(170, Cian)))
                    g.DrawPolygon(pen, Chaflan(r, 9));
            if (llena)
                using (var b = new SolidBrush(Cian)) g.FillRectangle(b, r.X, r.Y, 4, r.Height);
            int x = r.X + 82;
            if (llena)
                using (var b = new SolidBrush(Color.FromArgb(230, 236, 250)))
                    g.DrawString(Path.GetFileName(ranura.Ruta), mono, b, new RectangleF(x, r.Y + 11, r.Right - 86 - x, 14), recortado);
            else
            {
                using (var b = new SolidBrush(Color.FromArgb(120, 132, 165)))
                    g.DrawString(T("Arrastra la ISO o haz clic"), mono, b, x, r.Y + 11, StringFormat.GenericTypographic);
                using (var pen = new Pen(Color.FromArgb(200, 90, 110, 150)) { DashPattern = new[] { 4f, 3f } })
                    g.DrawLine(pen, x, r.Y + 25, r.Right - 26, r.Y + 25);
            }
        }

        string EstadoBoton
        {
            get
            {
                if (trabajando || Pendientes == 0 || configAbierta) return "inactivo";
                if (sobre != Zona.Boton) return "normal";
                return apretada == Zona.Boton ? "presionado" : "hover";
            }
        }

        // El brillo que cruza el botón y la línea de abajo (la imagen del botón ya está dibujada).
        void PintarBoton(Graphics g)
        {
            bool activo = EstadoBoton != "inactivo";
            if (activo)
            {
                // un brillo cruza el botón cada tanto
                double ciclo = tiempo % 3.2;
                if (ciclo < 0.8)
                {
                    GraphicsState estadoG = g.Save();
                    using (var forma = new GraphicsPath())
                    {
                        forma.AddPolygon(Diseno.BotonForma);
                        g.SetClip(forma, CombineMode.Intersect);
                        float x = Diseno.Boton.X - 20 + (float)(ciclo / 0.8) * (Diseno.Boton.Width + 40);
                        int top = Diseno.Boton.Y, bottom = Diseno.Boton.Bottom;
                        using (var b = new SolidBrush(Color.FromArgb(80, 210, 250, 255)))
                            g.FillPolygon(b, new[] { new PointF(x, top), new PointF(x + 16, top), new PointF(x - 8, bottom), new PointF(x - 24, bottom) });
                    }
                    g.Restore(estadoG);
                }
            }
            int pendientes = Pendientes;
            string sub = trabajando ? T("TRABAJANDO...")
                : !traduccion && !ConDefinitiva ? T("ELIGE QUÉ APLICAR")
                : pendientes == 0 ? T("ELIGE UNA ISO")
                : Etiqueta() + "  //  " + (pendientes == 1 ? T("1 DISCO") : T("{0} DISCOS", pendientes));
            SizeF medida = g.MeasureString(sub, monoChica, PointF.Empty, StringFormat.GenericTypographic);
            using (var b = new SolidBrush(activo ? Color.FromArgb(230, 170, 230, 255) : Color.FromArgb(120, 126, 146)))
                g.DrawString(sub, monoChica, b, Diseno.Boton.X + (Diseno.Boton.Width - medida.Width) / 2, Diseno.Boton.Y + 29, StringFormat.GenericTypographic);
        }

        void PintarProgreso(Graphics g)
        {
            Rectangle p = Diseno.Progreso;
            float ancho = p.Width / (float)Diseno.Segmentos;
            int llenos = progreso * Diseno.Segmentos / 100;
            for (int k = 0; k < Diseno.Segmentos; k++)
            {
                float t = k / (float)Diseno.Segmentos;
                Color c = k < llenos
                    ? Color.FromArgb((int)(Cian.R + (Violeta.R - Cian.R) * t), (int)(Cian.G + (Violeta.G - Cian.G) * t), (int)(Cian.B + (Violeta.B - Cian.B) * t))
                    : Color.FromArgb(230, 24, 30, 60);
                using (var b = new SolidBrush(c)) g.FillRectangle(b, p.X + k * ancho, p.Y, ancho - 2, p.Height);
            }
            if (trabajando || progreso > 0)
                using (var b = new SolidBrush(Color.FromArgb(240, 248, 255)))
                    g.DrawString(progreso + "%", monoGrande, b, p.Right + 6, p.Y - 1, StringFormat.GenericTypographic);
        }

        void PintarRegistro(Graphics g)
        {
            Rectangle r = Diseno.Registro;
            var lineas = registro.Skip(Math.Max(0, registro.Count - 3)).ToList();
            float fin = r.X;
            for (int i = 0; i < lineas.Count; i++)
            {
                bool ultima = i == lineas.Count - 1;
                string texto = "> " + lineas[i];
                using (var b = new SolidBrush(ultima ? Color.FromArgb(205, 232, 255) : Color.FromArgb(130, 150, 180)))
                    g.DrawString(texto, mono, b, new RectangleF(r.X, r.Y + i * 13, r.Width - 10, 13), recortado);
                if (ultima) fin = r.X + Math.Min(g.MeasureString(texto, mono, PointF.Empty, StringFormat.GenericTypographic).Width, r.Width - 10);
            }
            if ((int)(tiempo * 2.5) % 2 == 0 && lineas.Count > 0)
                using (var b = new SolidBrush(Cian)) g.FillRectangle(b, fin + 3, r.Y + (lineas.Count - 1) * 13 + 1, 5, 10);
        }

        void PintarScroller(Graphics g)
        {
            // en píxeles de la ventana, en rebanadas de 2 que suben y bajan
            Bitmap tira = Arte.Rotulo("scroller", null);
            Rectangle s = Px(Diseno.Scroller);
            GraphicsState estado = g.Save();
            g.SetClip(new Rectangle(s.X, s.Y + 1, s.Width, s.Height - 1), CombineMode.Intersect);
            int desplazamiento = (int)(tiempo * 55 * Diseno.Escala) % tira.Width;
            for (int x = 0; x < s.Width; x += 2)
            {
                int sx = (x + desplazamiento) % tira.Width, w = Math.Min(2, tira.Width - sx);
                int dy = (int)Math.Round(Math.Sin(x / Diseno.Escala * 0.03 + tiempo * 3.0) * 2.5 * Diseno.Escala);
                g.DrawImage(tira, new Rectangle(x, s.Y + Px(1) + dy, w, tira.Height), sx, 0, w, tira.Height, GraphicsUnit.Pixel);
            }
            g.Restore(estado);
        }

        // ---- La configuración de la Definitive Edition ----

        static Rectangle PerfilZona(int k) { return new Rectangle(PerfilX + k * PerfilPaso, PerfilY, PerfilAncho, PerfilAlto); }

        Rectangle FilaZona(int i) { return Rectangle.FromLTRB(28, filas[i] - 2, 466, filas[i] + 14); }

        static Rectangle FlechaZona(int y, bool mas) { return mas ? Rectangle.FromLTRB(448, y - 2, 466, y + 14) : Rectangle.FromLTRB(392, y - 2, 410, y + 14); }

        // Texto con espacio entre letras, como los títulos del arte.
        static float Espaciado(Graphics g, string texto, Font f, Brush b, float x, float y, float espacio, bool medir = false)
        {
            foreach (char c in texto)
            {
                string s = c.ToString();
                if (!medir) g.DrawString(s, f, b, x, y, StringFormat.GenericTypographic);
                x += (c == ' ' ? f.Size * 0.3f : g.MeasureString(s, f, PointF.Empty, StringFormat.GenericTypographic).Width) + espacio;
            }
            return x;
        }

        void PintarConfig(Graphics g)
        {
            using (var sombra = new SolidBrush(Color.FromArgb(205, 2, 4, 12))) g.FillRectangle(sombra, 0, 25, Diseno.Ancho, 362);
            using (var halo = new Pen(Color.FromArgb(60, Cian), 5)) g.DrawPolygon(halo, Chaflan(Panel, 12));
            Caja(g, Panel, 12, Color.FromArgb(235, 6, 10, 28), Color.FromArgb(170, Cian));

            string titulo = T("DEFINITIVE EDITION  //  CONFIGURACIÓN");
            float ancho = Espaciado(g, titulo, fTitulo, null, 0, 0, 2.6f, true);
            float tx = (Diseno.Ancho - ancho) / 2;
            using (var brillo = new SolidBrush(Color.FromArgb(90, Cian)))
            {
                Espaciado(g, titulo, fTitulo, brillo, tx - 0.6f, 39.4f, 2.6f);
                Espaciado(g, titulo, fTitulo, brillo, tx + 0.6f, 40.6f, 2.6f);
            }
            using (var b = new SolidBrush(Color.FromArgb(225, 250, 255))) Espaciado(g, titulo, fTitulo, b, tx, 40, 2.6f);
            using (var p = new Pen(Color.FromArgb(150, Cian)))
            {
                g.DrawLine(p, 30, 48, tx - 10, 48);
                g.DrawLine(p, tx + ancho + 6, 48, 730, 48);
            }

            // perfiles
            using (var b = new SolidBrush(Color.FromArgb(200, Cian))) g.DrawString(T("PERFIL"), monoChica, b, 30, 68, StringFormat.GenericTypographic);
            PerfilDe actual = PerfilActual();
            for (int k = 0; k < de.Perfiles.Count; k++)
            {
                PerfilDe p = de.Perfiles[k];
                Rectangle r = PerfilZona(k);
                bool elegido = actual == p, base_ = actual == null && p.Id == perfilBase, encima = sobre == Zona.Perfil && sobreIndice == k;
                Color relleno = elegido ? Color.FromArgb(24, 90, 150) : base_ ? Color.FromArgb(14, 36, 70) : encima ? Color.FromArgb(18, 40, 80) : Color.FromArgb(10, 16, 36);
                Caja(g, r, 5, relleno, encima ? Color.White : Color.FromArgb(elegido ? 255 : 90, Cian));
                string nombre = p.Nombre[Idioma].ToUpper();
                SizeF m = g.MeasureString(nombre, fNegrita, PointF.Empty, StringFormat.GenericTypographic);
                using (var b = new SolidBrush(elegido || encima ? Color.White : Color.FromArgb(170, 190, 220)))
                    g.DrawString(nombre, fNegrita, b, r.X + (r.Width - m.Width) / 2, r.Y + 4, StringFormat.GenericTypographic);
                if (p.Id == "definitiva")
                    using (var b = new SolidBrush(Color.FromArgb(255, 210, 120))) g.DrawString("★", fSimbolo, b, r.Right - 14, r.Y + 2, StringFormat.GenericTypographic);
            }
            var chip = new Rectangle(PerfilZona(de.Perfiles.Count).X + 4, 64, 102, 18);
            Caja(g, chip, 4, actual == null ? Color.FromArgb(60, 40, 14) : Color.FromArgb(10, 14, 28), actual == null ? Ambar : Color.FromArgb(70, 80, 110));
            using (var b = new SolidBrush(actual == null ? Ambar : Color.FromArgb(80, 90, 120)))
                g.DrawString(T("PERSONALIZADA"), fNegrita, b, chip.X + 8, chip.Y + 2, StringFormat.GenericTypographic);

            // lista de cambios
            Caja(g, Lista, 8, Color.FromArgb(230, 4, 7, 20), Color.FromArgb(70, Cian));
            using (var violeta = new SolidBrush(Violeta))
            using (var linea = new Pen(Color.FromArgb(90, Violeta)))
                foreach (var e in encabezados)
                {
                    string nombre = de.Grupos[e.Key][Idioma].ToUpper();
                    g.DrawString(nombre, fGrupo, violeta, 34, e.Value, StringFormat.GenericTypographic);
                    float w = g.MeasureString(nombre, fGrupo, PointF.Empty, StringFormat.GenericTypographic).Width;
                    g.DrawLine(linea, 38 + w, e.Value + 7, 460, e.Value + 7);
                }
            for (int i = 0; i < de.Opciones.Count; i++) PintarOpcion(g, i);

            // detalle de la opción bajo el ratón
            Caja(g, Detalle, 8, Color.FromArgb(230, 4, 7, 20), Color.FromArgb(70, Cian));
            using (var violeta = new SolidBrush(Violeta))
            using (var linea = new Pen(Color.FromArgb(90, Violeta)))
            {
                string d = T("DETALLE");
                g.DrawString(d, fGrupo, violeta, 494, 100, StringFormat.GenericTypographic);
                g.DrawLine(linea, 498 + g.MeasureString(d, fGrupo, PointF.Empty, StringFormat.GenericTypographic).Width, 107, 726, 107);
            }
            using (var b = new SolidBrush(Color.White)) g.DrawString(foco.Nombre[Idioma], fDetalleTitulo, b, 494, 116, StringFormat.GenericTypographic);
            var texto = new RectangleF(494, 135, 230, 110);
            using (var b = new SolidBrush(Color.FromArgb(200, 215, 240))) g.DrawString(foco.Descripcion[Idioma], fDetalle, b, texto);
            if (!foco.Probada)
            {
                float alto = g.MeasureString(foco.Descripcion[Idioma], fDetalle, (int)texto.Width).Height;
                using (var b = new SolidBrush(Ambar))
                    g.DrawString(T("Todavía no se probó en el juego: no viene en ningún perfil, pero puedes activarlo a mano."),
                                 fDetalle, b, new RectangleF(494, 135 + alto + 6, 230, 44));
            }

            // el perfil (el que está bajo el ratón, o el elegido)
            PerfilDe vista = sobre == Zona.Perfil && sobreIndice >= 0 ? de.Perfiles[sobreIndice] : actual;
            using (var p = new Pen(Color.FromArgb(50, Cian))) g.DrawLine(p, 494, 256, 726, 256);
            string cabeza = vista != null ? T("PERFIL {0}", vista.Nombre[Idioma].ToUpper()) : T("PERFIL PERSONALIZADO");
            string cuerpo = vista != null ? vista.Descripcion[Idioma] : T("Partiendo de {0}, con tus cambios.", de.Perfil(perfilBase).Nombre[Idioma]);
            using (var b = new SolidBrush(Color.FromArgb(230, Cian))) g.DrawString(cabeza, fGrupo, b, 494, 262, StringFormat.GenericTypographic);
            using (var b = new SolidBrush(Color.FromArgb(150, 165, 200))) g.DrawString(cuerpo, fPerfil, b, new RectangleF(494, 276, 232, 70));

            using (var b = new SolidBrush(Color.FromArgb(230, 150, 175, 215)))
                g.DrawString(T("> Clic en una casilla para activarla.  Clic en ‹ › para cambiar cuánto."), monoChica, b, 28, 361, StringFormat.GenericTypographic);
        }

        void PintarOpcion(Graphics g, int i)
        {
            OpcionDe o = de.Opciones[i];
            int y = filas[i], n = NivelDe(o.Id);
            bool encima = (sobre == Zona.Opcion || sobre == Zona.NivelMenos || sobre == Zona.NivelMas) && sobreIndice == i;
            if (encima || o == foco)
            {
                using (var b = new SolidBrush(encima ? Color.FromArgb(200, 20, 60, 110) : Color.FromArgb(120, 20, 50, 90))) g.FillRectangle(b, 28, y - 2, 438, 15);
                using (var b = new SolidBrush(Cian)) g.FillRectangle(b, 28, y - 2, 2, 15);
            }
            Casilla(g, 38, y + 1.5f, n > 0, 9);
            string nombre = o.Nombre[Idioma];
            using (var b = new SolidBrush(n > 0 ? Color.FromArgb(235, 242, 255) : Color.FromArgb(130, 142, 170)))
                g.DrawString(nombre, fOpcion, b, 54, y, StringFormat.GenericTypographic);
            if (!o.Probada)
            {
                float cx = 54 + g.MeasureString(nombre, fOpcion, PointF.Empty, StringFormat.GenericTypographic).Width + 8;
                string prueba = T("EN PRUEBA");
                float w = g.MeasureString(prueba, fChip, PointF.Empty, StringFormat.GenericTypographic).Width + 8;
                using (var b = new SolidBrush(Color.FromArgb(70, 46, 10))) g.FillRectangle(b, cx, y + 1, w, 11);
                using (var b = new SolidBrush(Ambar)) g.DrawString(prueba, fChip, b, cx + 4, y + 2, StringFormat.GenericTypographic);
            }
            if (o.Niveles.Count == 0) return;
            string etiqueta = o.Niveles[Math.Max(n, 1) - 1][Idioma];
            using (var flecha = new SolidBrush(Color.FromArgb(n > 0 ? 255 : 80, Cian)))
            {
                g.FillPolygon(flecha, new[] { new PointF(400, y + 6.5f), new PointF(405, y + 3), new PointF(405, y + 10) });
                g.FillPolygon(flecha, new[] { new PointF(458, y + 6.5f), new PointF(453, y + 3), new PointF(453, y + 10) });
            }
            SizeF m = g.MeasureString(etiqueta, fNivel, PointF.Empty, StringFormat.GenericTypographic);
            using (var b = new SolidBrush(n > 0 ? Color.FromArgb(235, 250, 255) : Color.FromArgb(90, 100, 130)))
                g.DrawString(etiqueta, fNivel, b, 429 - m.Width / 2, y, StringFormat.GenericTypographic);
        }

        // ---- Ratón y teclado ----

        Zona Buscar(Point enVentana, out int indice)
        {
            indice = -1;
            var p = new Point((int)(enVentana.X / Diseno.Escala), (int)(enVentana.Y / Diseno.Escala));
            if (Diseno.Minimizar.Contains(p)) return Zona.Minimizar;
            if (Diseno.Cerrar.Contains(p)) return Zona.Cerrar;
            for (int k = 0; k < 2; k++)
                if (Diseno.Idiomas[k].Contains(p))
                {
                    indice = k;
                    return Zona.Idioma;
                }
            if (Diseno.Musica.Contains(p)) return Zona.Musica;
            if (Diseno.Leeme.Contains(p)) return Zona.Leeme;
            if (Diseno.Salir.Contains(p)) return Zona.Salir;
            if (configAbierta)
            {
                for (int k = 0; k < de.Perfiles.Count; k++)
                    if (PerfilZona(k).Contains(p))
                    {
                        indice = k;
                        return Zona.Perfil;
                    }
                for (int i = 0; i < filas.Count; i++)
                {
                    if (!FilaZona(i).Contains(p)) continue;
                    indice = i;
                    if (de.Opciones[i].Niveles.Count > 0 && FlechaZona(filas[i], false).Contains(p)) return Zona.NivelMenos;
                    if (de.Opciones[i].Niveles.Count > 0 && FlechaZona(filas[i], true).Contains(p)) return Zona.NivelMas;
                    return Zona.Opcion;
                }
                if (Diseno.Restablecer.Contains(p)) return Zona.Restablecer;
                if (Diseno.Listo.Contains(p)) return Zona.Listo;
                return Zona.Nada;
            }
            if (Diseno.Ranuras[0].Contains(p)) return Zona.Ranura1;
            if (Diseno.Ranuras[1].Contains(p)) return Zona.Ranura2;
            if (Diseno.Boton.Contains(p)) return Zona.Boton;
            if (Diseno.ModuloTraduccion.Contains(p)) return Zona.Traduccion;
            if (de != null && EngranajeZona.Contains(p)) return Zona.Engranaje;
            if (de != null && Diseno.ModuloDe.Contains(p)) return Zona.Definitiva;
            return Zona.Nada;
        }

        bool Habilitada(Zona z)
        {
            switch (z)
            {
                case Zona.Ranura1:
                case Zona.Ranura2:
                case Zona.Traduccion:
                case Zona.Definitiva:
                case Zona.Engranaje:
                    return !trabajando;
                case Zona.Boton:
                    return !trabajando && Pendientes > 0;
                default:
                    return z != Zona.Nada;
            }
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            int indice;
            Zona z = Buscar(e.Location, out indice);
            if (z == sobre && indice == sobreIndice) return;
            sobre = z;
            sobreIndice = indice;
            if (configAbierta && indice >= 0 && (z == Zona.Opcion || z == Zona.NivelMenos || z == Zona.NivelMas)) foco = de.Opciones[indice];
            if (Habilitada(z)) Sonidos.Tocar("hover");
            Cursor = z != Zona.Nada ? Cursors.Hand : Cursors.Default;
            Invalidate();
        }

        protected override void OnMouseLeave(EventArgs e)
        {
            sobre = Zona.Nada;
            sobreIndice = -1;
            Invalidate();
        }

        protected override void OnMouseDown(MouseEventArgs e)
        {
            if (e.Button != MouseButtons.Left) return;
            int indice;
            Zona z = Buscar(e.Location, out indice);
            if (z == Zona.Nada)
            {
                ReleaseCapture();
                SendMessage(Handle, 0xA1, (IntPtr)2, IntPtr.Zero);  // arrastrar la ventana (WM_NCLBUTTONDOWN, HTCAPTION)
                return;
            }
            apretada = z;
            apretadaIndice = indice;
            Invalidate();
        }

        protected override void OnMouseUp(MouseEventArgs e)
        {
            Zona z = apretada;
            int indice = apretadaIndice, ahora;
            apretada = Zona.Nada;
            Invalidate();
            if (z != Zona.Nada && z == Buscar(e.Location, out ahora) && ahora == indice) Accion(z, indice);
        }

        protected override void OnKeyDown(KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Escape)
            {
                if (configAbierta) CerrarConfig();
                else Close();
            }
            else if (e.KeyCode == Keys.Enter)
            {
                if (configAbierta) CerrarConfig();
                else Aplicar();
            }
            else if (e.KeyCode == Keys.M) CambiarMusica();
        }

        protected override void OnDragEnter(DragEventArgs e)
        {
            e.Effect = !trabajando && e.Data.GetDataPresent(DataFormats.FileDrop) ? DragDropEffects.Copy : DragDropEffects.None;
        }

        protected override void OnDragDrop(DragEventArgs e)
        {
            foreach (string path in ((string[])e.Data.GetData(DataFormats.FileDrop)).Take(2)) Asignar(path, -1, true);
        }

        void Accion(Zona z, int indice)
        {
            switch (z)
            {
                case Zona.Minimizar:
                    Sonidos.Tocar("click");
                    WindowState = FormWindowState.Minimized;
                    break;
                case Zona.Cerrar:
                case Zona.Salir:
                    Sonidos.Tocar("click");
                    Close();
                    break;
                case Zona.Idioma:
                    CambiarIdioma(indice);
                    break;
                case Zona.Ranura1:
                case Zona.Ranura2:
                    Elegir(z == Zona.Ranura1 ? 0 : 1);
                    break;
                case Zona.Boton:
                    Aplicar();
                    break;
                case Zona.Musica:
                    CambiarMusica();
                    break;
                case Zona.Leeme:
                    Sonidos.Tocar("click");
                    AbrirLeeme();
                    break;
                case Zona.Traduccion:
                case Zona.Definitiva:
                    if (trabajando)
                    {
                        Sonidos.Tocar("error");
                        break;
                    }
                    Sonidos.Tocar("click");
                    if (z == Zona.Traduccion) traduccion = !traduccion;
                    else definitiva = !definitiva;
                    break;
                case Zona.Engranaje:
                    if (trabajando)
                    {
                        Sonidos.Tocar("error");
                        break;
                    }
                    Sonidos.Tocar("click");
                    configAbierta = true;
                    break;
                case Zona.Perfil:
                    Sonidos.Tocar("click");
                    ElegirPerfil(de.Perfiles[indice].Id);
                    definitiva = true;
                    break;
                case Zona.Opcion:
                case Zona.NivelMenos:
                case Zona.NivelMas:
                    CambiarOpcion(de.Opciones[indice], z);
                    break;
                case Zona.Restablecer:
                    Sonidos.Tocar("click");
                    ElegirPerfil("definitiva");
                    definitiva = true;
                    break;
                case Zona.Listo:
                    CerrarConfig();
                    break;
            }
            Invalidate();
        }

        // ---- Acciones ----

        void CambiarOpcion(OpcionDe o, Zona z)
        {
            Sonidos.Tocar("click");
            int n = NivelDe(o.Id), max = o.CantidadNiveles, recordado;
            if (z == Zona.Opcion)
                n = n > 0 ? 0 : recordados.TryGetValue(o.Id, out recordado) ? recordado : 1;
            else if (z == Zona.NivelMas)
                n = n <= 0 || n >= max ? 1 : n + 1;
            else
                n = n <= 1 ? max : n - 1;
            niveles[o.Id] = n;
            if (n > 0)
            {
                recordados[o.Id] = n;
                definitiva = true;
            }
            PerfilDe p = PerfilActual();
            if (p != null) perfilBase = p.Id;
            foco = o;
        }

        void CerrarConfig()
        {
            Sonidos.Tocar("click");
            configAbierta = false;
            Invalidate();
        }

        void CambiarIdioma(int idioma)
        {
            Sonidos.Tocar("click");
            if (Idioma == idioma) return;
            Idioma = idioma;
            Text = T(Titulo);
            if (registroInicial) Bienvenida();
            Invalidate();
        }

        void Elegir(int i)
        {
            if (trabajando)
            {
                Sonidos.Tocar("error");
                return;
            }
            Sonidos.Tocar("click");
            using (var d = new OpenFileDialog())
            {
                d.Title = T("Elige la ISO del disco {0}", i + 1);
                d.Filter = T("Imágenes ISO (*.iso)|*.iso|Todos los archivos (*.*)|*.*");
                if (d.ShowDialog(this) == DialogResult.OK) Asignar(d.FileName, i, true);
            }
        }

        void Asignar(string path, int preferida, bool sonido)
        {
            if (trabajando) return;
            int disc;
            Cursor.Current = Cursors.WaitCursor;  // una ISO ya traducida se revisa entera: tarda unos segundos
            string estado, mensaje = Detectar(path, manifest, out disc, out estado);
            int i = disc > 0 ? disc - 1 : preferida >= 0 ? preferida : ranuras[0].Ruta == null ? 0 : 1;
            ranuras[i] = new Ranura { Ruta = path, Estado = estado };
            foreach (string linea in mensaje.Split('\n')) Registrar(linea);
            if (sonido) Sonidos.Tocar(estado == "original" || estado == "traducida" ? "click" : "error");
            Invalidate();
        }

        void Aplicar()
        {
            if (trabajando || configAbierta) return;
            List<Ranura> trabajos = traduccion || ConDefinitiva ? ranuras.Where(Aplicable).ToList() : new List<Ranura>();
            if (trabajos.Count == 0)
            {
                Sonidos.Tocar("error");
                Registrar(!traduccion && !ConDefinitiva ? T("Marca la traducción, la Definitive Edition o las dos.")
                          : ranuras.Any(r => r.Ruta != null) ? T("No hay ninguna ISO original para parchear.")
                          : T("Primero elige al menos una ISO."));
                return;
            }
            Sonidos.Tocar("inicio");
            trabajando = true;
            Cancelar = false;
            enCurso = SeleccionActual();
            revelada = -1;
            Avance(0);
            foreach (Ranura r in trabajos) r.Estado = "encurso";
            Invalidate();
            Seleccion sel = enCurso;
            new Thread(() => Trabajar(trabajos, sel)) { IsBackground = true }.Start();
        }

        // En el hilo de trabajo.
        void Trabajar(List<Ranura> trabajos, Seleccion sel)
        {
            bool ok = true;
            try
            {
                Dictionary<string, List<PatchEntry>> m;
                using (ZipArchive zip = OpenPackage(out m))
                    for (int i = 0; i < trabajos.Count; i++)
                    {
                        Ranura r = trabajos[i];
                        Resultado resultado;
                        try { resultado = Process(r.Ruta, null, zip, m, de, sel, new AvisoVentana(this, i, trabajos.Count)); }
                        catch (OperationCanceledException)
                        {
                            EnLaVentana(() => { r.Estado = "error"; Registrar(T("Cancelado.")); });
                            ok = false;
                            break;
                        }
                        EnLaVentana(() => r.Estado = resultado == Resultado.Error ? "error" : resultado == Resultado.Lista ? "lista" : "traducida");
                        ok &= resultado != Resultado.Error;
                    }
            }
            catch (Exception ex)
            {
                EnLaVentana(() => Registrar(T("Error inesperado: {0}", ex.Message)));
                ok = false;
            }
            EnLaVentana(() => Termino(ok));
        }

        void Termino(bool ok)
        {
            trabajando = false;
            Sonidos.Tocar(ok ? "ok" : "error");
            if (ok)
            {
                Avance(100);
                Registrar(T("Terminado: ya puedes jugar con las ISO nuevas."));
                if (enCurso.Traduccion) revelada = tiempo;  // la frase queda en español, con un destello
            }
            Invalidate();
            if (cerrarAlTerminar) Close();
        }

        void CambiarMusica()
        {
            if (musica == null || !musica.Disponible)
            {
                Sonidos.Tocar("error");
                Registrar(T("En este equipo no se puede reproducir la música."));
                return;
            }
            nivel = (nivel + 1) % 6;
            musica.Nivel(nivel);
            Sonidos.Tocar("click");
            Invalidate(Px(Diseno.Musica));
        }

        // El LEEME en español o el README en inglés, según el idioma (o el otro, si falta).
        void AbrirLeeme()
        {
            string carpeta = Path.GetDirectoryName(Application.ExecutablePath);
            string[] nombres = Idioma == 0 ? new[] { "LEEME.txt", "README.txt" } : new[] { "README.txt", "LEEME.txt" };
            string leeme = nombres.Select(n => Path.Combine(carpeta, n)).FirstOrDefault(File.Exists);
            try
            {
                if (leeme != null) System.Diagnostics.Process.Start(leeme);
                else Registrar(T("No está el LEEME.txt junto al programa."));
            }
            catch (System.ComponentModel.Win32Exception) { Registrar(T("No se pudo abrir el LEEME.txt.")); }
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            if (trabajando)
            {
                e.Cancel = true;
                if (!cerrarAlTerminar && Dialogo.Preguntar(this, T("Se está creando una ISO. ¿Cancelar y salir? Lo que se creó hasta ahora se borra.")))
                {
                    Cancelar = true;
                    cerrarAlTerminar = true;
                    Registrar(T("Cancelando..."));
                }
                return;
            }
            animacion.Stop();
            if (musica != null) musica.Cerrar();
            base.OnFormClosing(e);
        }

        // Imágenes de la ventana sin mostrarla (--captura): trabajando, esperando con un disco elegido
        // (con ISO, muestra cómo quedan elegidas, para probar la detección), la configuración y la
        // ventana en el otro idioma con la frase ya traducida.
        public static bool Capturar(string path, List<string> isos)
        {
            string carpeta = Path.GetDirectoryName(Path.GetFullPath(path)), nombre = Path.GetFileNameWithoutExtension(path);
            using (var v = new Ventana(new string[0]))
            {
                v.ranuras[0] = new Ranura { Ruta = @"C:\Juegos\PS2\Xenosaga2UNDUB1.iso", Estado = "encurso" };
                v.traduccion = true;
                v.definitiva = v.de != null;
                v.trabajando = true;
                v.enCurso = v.SeleccionActual();
                v.progreso = 47;
                v.tiempo = 0.35;
                v.sobre = Zona.Leeme;
                v.Registrar(T("Disco {0}: comprobando los archivos...", 1));
                v.Registrar(T("Disco {0}: creando \"{1}\"...", 1, "Xenosaga2UNDUB1" + T(" (Español + Definitive)") + ".iso"));
                v.Guardar(path);
                v.ranuras[0].Estado = "original";
                v.ranuras[1] = new Ranura { Ruta = @"C:\Juegos\PS2\Otro juego.iso", Estado = "novalida" };
                v.trabajando = false;
                v.progreso = 0;
                v.tiempo = 0.5;
                v.sobre = Zona.Boton;
                v.Registrar(T("No es Xenosaga Episode II en versión americana (NTSC-U)."));
                if (isos.Count > 0)
                {
                    v.ranuras[0] = new Ranura();
                    v.ranuras[1] = new Ranura();
                    foreach (string iso in isos) v.Asignar(iso, -1, false);
                }
                v.Guardar(Path.Combine(carpeta, nombre + "_espera.png"));
                if (v.de != null)
                {
                    v.configAbierta = true;
                    v.niveles["vida_jefes"] = 1;
                    v.foco = v.de.Opcion("break_corto");
                    v.sobre = Zona.Opcion;
                    v.sobreIndice = v.de.Opciones.IndexOf(v.foco);
                    v.Guardar(Path.Combine(carpeta, nombre + "_config.png"));
                    v.configAbierta = false;
                    v.niveles["vida_jefes"] = 0;
                }
                int idioma = Idioma;
                Idioma = 1 - idioma;
                v.sobre = Zona.Nada;
                v.ranuras[0].Estado = "lista";
                v.ranuras[1] = new Ranura();
                v.progreso = 100;
                v.revelada = 0;
                v.tiempo = 3;
                v.Bienvenida();
                v.Registrar(T("Terminado: ya puedes jugar con las ISO nuevas."));
                v.Guardar(Path.Combine(carpeta, nombre + "_" + Sigla + ".png"));
                Idioma = idioma;
            }
            return true;
        }

        void Guardar(string path)
        {
            using (var b = new Bitmap(fondo.Width, fondo.Height))
            {
                using (Graphics g = Graphics.FromImage(b)) Pintar(g, new Rectangle(Point.Empty, fondo.Size));
                b.Save(path, ImageFormat.Png);
            }
        }
    }

    // Pregunta de sí o no con el mismo estilo que la ventana.
    class Dialogo : Form
    {
        readonly Arte arte;
        readonly Sonidos sonidos;
        readonly string texto;
        readonly Rectangle si, no;
        readonly Font letra = new Font("Segoe UI", 13f, GraphicsUnit.Pixel);
        readonly Font mono = new Font("Consolas", 10f, GraphicsUnit.Pixel);
        string sobre, apretado;

        Dialogo(Ventana ventana, string texto)
        {
            arte = ventana.Arte;
            sonidos = ventana.Sonidos;
            this.texto = texto;
            FormBorderStyle = FormBorderStyle.None;
            StartPosition = FormStartPosition.CenterParent;
            ShowInTaskbar = false;
            ClientSize = new Size(Px(Ancho), Px(Alto));
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer, true);
            KeyPreview = true;
            no = new Rectangle(Ancho - 16 - 84, Alto - 14 - 22, 84, 22);  // medidas de diseño, como la ventana
            si = new Rectangle(no.X - 10 - 84, no.Y, 84, 22);
        }

        const int Ancho = 420, Alto = 150;

        public static bool Preguntar(Ventana ventana, string texto)
        {
            using (var d = new Dialogo(ventana, texto))
                return d.ShowDialog(ventana) == DialogResult.Yes;
        }

        protected override CreateParams CreateParams
        {
            get
            {
                CreateParams cp = base.CreateParams;
                cp.ClassStyle |= 0x20000;  // CS_DROPSHADOW
                return cp;
            }
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
            GraphicsState estado = g.Save();
            g.ScaleTransform(Diseno.Escala, Diseno.Escala);
            var todo = new Rectangle(0, 0, Ancho, Alto);
            using (var fondo = new LinearGradientBrush(todo, Color.FromArgb(12, 16, 42), Color.FromArgb(4, 6, 16), 90f))
                g.FillRectangle(fondo, todo);
            using (var barra = new SolidBrush(Color.FromArgb(4, 6, 16))) g.FillRectangle(barra, 0, 0, Ancho, 22);
            using (var cian = new Pen(Color.FromArgb(120, 90, 220, 255))) g.DrawLine(cian, 0, 22, Ancho, 22);
            using (var borde = new Pen(Color.FromArgb(200, 210, 230))) g.DrawRectangle(borde, 0, 0, Ancho - 1, Alto - 1);
            using (var cian = new SolidBrush(Color.FromArgb(230, 90, 220, 255)))
                g.DrawString((Edicion == "es" ? "XS2·ES" : "XS2·DE") + "  //  " + T("CONFIRMAR"), mono, cian, 10, 6, StringFormat.GenericTypographic);
            using (var blanco = new SolidBrush(Color.FromArgb(232, 238, 250)))
                g.DrawString(texto, letra, blanco, new RectangleF(18, 36, Ancho - 36, 64));
            g.Restore(estado);
            Boton(g, "si", si);
            Boton(g, "no", no);
        }

        void Boton(Graphics g, string nombre, Rectangle r)
        {
            string estado = apretado == nombre && sobre == nombre ? "presionado" : sobre == nombre ? "hover" : "normal";
            Dibujar(g, arte.Rotulo(nombre, estado), r.X, r.Y);
        }

        string Buscar(Point enVentana)
        {
            var p = new Point((int)(enVentana.X / Diseno.Escala), (int)(enVentana.Y / Diseno.Escala));
            return si.Contains(p) ? "si" : no.Contains(p) ? "no" : null;
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            string z = Buscar(e.Location);
            if (z == sobre) return;
            sobre = z;
            if (z != null) sonidos.Tocar("hover");
            Invalidate();
        }

        protected override void OnMouseDown(MouseEventArgs e)
        {
            apretado = Buscar(e.Location);
            Invalidate();
        }

        protected override void OnMouseUp(MouseEventArgs e)
        {
            string z = apretado;
            apretado = null;
            Invalidate();
            if (z != null && z == Buscar(e.Location)) Responder(z == "si");
        }

        protected override void OnKeyDown(KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Enter) Responder(true);
            else if (e.KeyCode == Keys.Escape) Responder(false);
        }

        void Responder(bool siONo)
        {
            sonidos.Tocar("click");
            DialogResult = siONo ? DialogResult.Yes : DialogResult.No;
        }
    }
}
