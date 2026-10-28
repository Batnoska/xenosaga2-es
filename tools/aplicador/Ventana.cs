// La ventana del aplicador, con estética de keygen de los 2000 y de Xenosaga Episode II.
//
// El arte, los sonidos y la música vienen de arte.zip y las medidas, de Diseno.cs; los dos los arma
// tools/aplicador/arte.py. El fondo está en dos capas para que el brillo de la gema del Zohar
// lata entre ellas; lo demás (ranuras, botón, progreso, registro, créditos) se dibuja encima.
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
            if (s == null) throw new InvalidDataException("al programa le falta el arte");
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
    }

    // De medidas de diseño (las de arte.py y Diseno.cs) a píxeles de la ventana.
    static int Px(float v) { return (int)Math.Round(v * Diseno.Escala); }
    static Rectangle Px(Rectangle r) { return Rectangle.FromLTRB(Px(r.Left), Px(r.Top), Px(r.Right), Px(r.Bottom)); }

    // Una imagen en su tamaño real, en una posición de diseño.
    static void Dibujar(Graphics g, Bitmap b, float x, float y)
    {
        g.DrawImage(b, new Rectangle(Px(x), Px(y), b.Width, b.Height), 0, 0, b.Width, b.Height, GraphicsUnit.Pixel);
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
        static readonly int[] Volumen = { 0, 120, 250, 450, 700, 1000 };  // escala de MCI, niveles 0 a 5
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
        enum Zona { Nada, Minimizar, Cerrar, Ranura1, Ranura2, Boton, Musica, Leeme, Salir }

        [DllImport("user32.dll")]
        static extern bool ReleaseCapture();
        [DllImport("user32.dll")]
        static extern IntPtr SendMessage(IntPtr hWnd, int msg, IntPtr wParam, IntPtr lParam);

        static readonly Color Cian = Color.FromArgb(90, 220, 255), Violeta = Color.FromArgb(170, 120, 255);
        internal readonly Arte Arte;
        internal readonly Sonidos Sonidos;
        internal volatile bool Cancelar;
        readonly Bitmap fondo;  // las dos capas juntas, sin el brillo de la gema
        readonly Rectangle zonaGema;
        readonly Dictionary<string, List<PatchEntry>> manifest;
        readonly Ranura[] ranuras = { new Ranura(), new Ranura() };
        readonly List<string> registro = new List<string>();
        readonly System.Diagnostics.Stopwatch reloj = System.Diagnostics.Stopwatch.StartNew();
        readonly System.Windows.Forms.Timer animacion = new System.Windows.Forms.Timer { Interval = 33 };
        readonly Font mono = new Font("Consolas", 10f, GraphicsUnit.Pixel);
        readonly Font monoChica = new Font("Consolas", 9f, GraphicsUnit.Pixel);
        readonly Font monoGrande = new Font("Consolas", 11f, FontStyle.Bold, GraphicsUnit.Pixel);
        readonly StringFormat recortado = new StringFormat(StringFormat.GenericTypographic)
        {
            Trimming = StringTrimming.EllipsisCharacter,
            FormatFlags = StringFormatFlags.NoWrap,
        };
        Musica musica;
        Zona sobre, apretada;
        int nivel = 2, progreso;
        bool trabajando, cerrarAlTerminar;
        double tiempo;  // en segundos, para las animaciones

        public Ventana(IEnumerable<string> isos)
        {
            Arte = new Arte();
            Sonidos = new Sonidos(Arte);
            using (OpenPackage(out manifest)) { }
            fondo = new Bitmap(Px(Diseno.Ancho), Px(Diseno.Alto), PixelFormat.Format32bppPArgb);
            using (Graphics g = Graphics.FromImage(fondo))
            {
                Dibujar(g, Arte.Img["fondo_atras"], 0, 0);
                Dibujar(g, Arte.Img["fondo_frente"], 0, 0);
            }
            Bitmap gema = Arte.Img["gema"];
            zonaGema = new Rectangle(Px(Diseno.Gema.X) - gema.Width / 2, Px(Diseno.Gema.Y) - gema.Height / 2, gema.Width, gema.Height);

            Text = "Xenosaga Episode II en español";
            FormBorderStyle = FormBorderStyle.None;
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = fondo.Size;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.Opaque, true);
            AllowDrop = true;
            KeyPreview = true;
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); }
            catch (ArgumentException) { }
            animacion.Tick += (s, e) => Animar();

            Registrar("Arrastra las ISO a la ventana o haz clic en cada disco.");
            Registrar("Se crean copias en español: tus ISO no se modifican.");
            foreach (string iso in isos) Asignar(iso, -1, false);
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
            Invalidate(Px(Diseno.BotonZona));
            Invalidate(Px(Diseno.Registro));
        }

        // ---- Dibujo ----

        protected override void OnPaint(PaintEventArgs e) { Pintar(e.Graphics, e.ClipRectangle); }

        // Primero las imágenes, en píxeles de la ventana; después textos y formas, en medidas de
        // diseño con la escala aplicada (así quedan nítidos).
        void Pintar(Graphics g, Rectangle clip)
        {
            g.InterpolationMode = InterpolationMode.NearestNeighbor;
            g.PixelOffsetMode = PixelOffsetMode.Half;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
            g.DrawImage(fondo, clip, clip, GraphicsUnit.Pixel);
            if (clip.IntersectsWith(zonaGema)) PintarGema(g);
            if (clip.IntersectsWith(Px(Diseno.Scroller))) PintarScroller(g);
            for (int i = 0; i < 2; i++)
                if (ranuras[i].Ruta != null)
                    Dibujar(g, Arte.Img["chip_" + ranuras[i].Estado], Diseno.Ranuras[i].Right - 78, Diseno.Ranuras[i].Y + 8);
            Dibujar(g, Arte.Img["boton_" + EstadoBoton], Diseno.BotonZona.X, Diseno.BotonZona.Y);
            PintarBotonChico(g, "musica", Zona.Musica, Diseno.Musica);
            PintarBotonChico(g, "leeme", Zona.Leeme, Diseno.Leeme);
            PintarBotonChico(g, "salir", Zona.Salir, Diseno.Salir);
            PintarBotonChico(g, "minimizar", Zona.Minimizar, Diseno.Minimizar);
            PintarBotonChico(g, "cerrar", Zona.Cerrar, Diseno.Cerrar);

            GraphicsState estado = g.Save();
            g.ScaleTransform(Diseno.Escala, Diseno.Escala);
            for (int i = 0; i < 2; i++) PintarRanura(g, i);
            PintarBoton(g);
            PintarProgreso(g);
            PintarRegistro(g);
            for (int k = 0; k < 5; k++)
            {
                int h = 4 + k * 2;
                bool activa = musica != null && musica.Disponible && k < nivel;
                using (var b = new SolidBrush(activa ? Color.FromArgb(14, 16, 26) : Color.FromArgb(150, 70, 76, 96)))
                    g.FillRectangle(b, Diseno.Musica.X + 54 + k * 5, Diseno.Musica.Bottom - 6 - h, 3, h);
            }
            g.Restore(estado);
        }

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
                    g.DrawString("Arrastra la ISO o haz clic", mono, b, x, r.Y + 11, StringFormat.GenericTypographic);
                using (var pen = new Pen(Color.FromArgb(200, 90, 110, 150)) { DashPattern = new[] { 4f, 3f } })
                    g.DrawLine(pen, x, r.Y + 25, r.Right - 26, r.Y + 25);
            }
        }

        int Pendientes { get { return ranuras.Count(r => r.Estado == "original"); } }

        string EstadoBoton
        {
            get
            {
                if (trabajando || Pendientes == 0) return "inactivo";
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
            string sub = trabajando ? "TRABAJANDO..." : Pendientes == 0 ? "ELIGE UNA ISO" : Pendientes == 1 ? "INICIAR  //  1 DISCO" : "INICIAR  //  2 DISCOS";
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
            Bitmap tira = Arte.Img["scroller"];
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

        void PintarBotonChico(Graphics g, string nombre, Zona zona, Rectangle r)
        {
            string estado = apretada == zona && sobre == zona ? "presionado" : sobre == zona ? "hover" : "normal";
            Dibujar(g, Arte.Img[nombre + "_" + estado], r.X, r.Y);
        }

        // ---- Ratón y teclado ----

        Zona Buscar(Point enVentana)
        {
            var p = new Point((int)(enVentana.X / Diseno.Escala), (int)(enVentana.Y / Diseno.Escala));
            if (Diseno.Minimizar.Contains(p)) return Zona.Minimizar;
            if (Diseno.Cerrar.Contains(p)) return Zona.Cerrar;
            if (Diseno.Ranuras[0].Contains(p)) return Zona.Ranura1;
            if (Diseno.Ranuras[1].Contains(p)) return Zona.Ranura2;
            if (Diseno.Boton.Contains(p)) return Zona.Boton;
            if (Diseno.Musica.Contains(p)) return Zona.Musica;
            if (Diseno.Leeme.Contains(p)) return Zona.Leeme;
            if (Diseno.Salir.Contains(p)) return Zona.Salir;
            return Zona.Nada;
        }

        bool Habilitada(Zona z)
        {
            if (z == Zona.Ranura1 || z == Zona.Ranura2) return !trabajando;
            if (z == Zona.Boton) return !trabajando && Pendientes > 0;
            return z != Zona.Nada;
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            Zona z = Buscar(e.Location);
            if (z == sobre) return;
            sobre = z;
            if (Habilitada(z)) Sonidos.Tocar("hover");
            Cursor = z != Zona.Nada ? Cursors.Hand : Cursors.Default;
            Invalidate();
        }

        protected override void OnMouseLeave(EventArgs e)
        {
            sobre = Zona.Nada;
            Invalidate();
        }

        protected override void OnMouseDown(MouseEventArgs e)
        {
            if (e.Button != MouseButtons.Left) return;
            Zona z = Buscar(e.Location);
            if (z == Zona.Nada)
            {
                ReleaseCapture();
                SendMessage(Handle, 0xA1, (IntPtr)2, IntPtr.Zero);  // arrastrar la ventana (WM_NCLBUTTONDOWN, HTCAPTION)
                return;
            }
            apretada = z;
            Invalidate();
        }

        protected override void OnMouseUp(MouseEventArgs e)
        {
            Zona z = apretada;
            apretada = Zona.Nada;
            Invalidate();
            if (z != Zona.Nada && z == Buscar(e.Location)) Accion(z);
        }

        protected override void OnKeyDown(KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Escape) Close();
            else if (e.KeyCode == Keys.Enter) Aplicar();
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

        void Accion(Zona z)
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
            }
        }

        // ---- Acciones ----

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
                d.Title = "Elige la ISO del disco " + (i + 1);
                d.Filter = "Imágenes ISO (*.iso)|*.iso|Todos los archivos (*.*)|*.*";
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
            if (trabajando) return;
            List<Ranura> trabajos = ranuras.Where(r => r.Estado == "original").ToList();
            if (trabajos.Count == 0)
            {
                Sonidos.Tocar("error");
                Registrar(ranuras.Any(r => r.Ruta != null) ? "No hay ninguna ISO original para parchear." : "Primero elige al menos una ISO.");
                return;
            }
            Sonidos.Tocar("inicio");
            trabajando = true;
            Cancelar = false;
            Avance(0);
            foreach (Ranura r in trabajos) r.Estado = "encurso";
            Invalidate();
            new Thread(() => Trabajar(trabajos)) { IsBackground = true }.Start();
        }

        // En el hilo de trabajo.
        void Trabajar(List<Ranura> trabajos)
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
                        try { resultado = Process(r.Ruta, null, zip, m, new AvisoVentana(this, i, trabajos.Count)); }
                        catch (OperationCanceledException)
                        {
                            EnLaVentana(() => { r.Estado = "error"; Registrar("Cancelado."); });
                            ok = false;
                            break;
                        }
                        EnLaVentana(() => r.Estado = resultado == Resultado.Error ? "error" : resultado == Resultado.Lista ? "lista" : "traducida");
                        ok &= resultado != Resultado.Error;
                    }
            }
            catch (Exception ex)
            {
                EnLaVentana(() => Registrar("Error inesperado: " + ex.Message));
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
                Registrar("Terminado: ya puedes jugar con las ISO nuevas.");
            }
            Invalidate();
            if (cerrarAlTerminar) Close();
        }

        void CambiarMusica()
        {
            if (musica == null || !musica.Disponible)
            {
                Sonidos.Tocar("error");
                Registrar("En este equipo no se puede reproducir la música.");
                return;
            }
            nivel = (nivel + 1) % 6;
            musica.Nivel(nivel);
            Sonidos.Tocar("click");
            Invalidate(Px(Diseno.Musica));
        }

        void AbrirLeeme()
        {
            string leeme = Path.Combine(Path.GetDirectoryName(Application.ExecutablePath), "LEEME.txt");
            try
            {
                if (File.Exists(leeme)) System.Diagnostics.Process.Start(leeme);
                else Registrar("No está el LEEME.txt junto al programa.");
            }
            catch (System.ComponentModel.Win32Exception) { Registrar("No se pudo abrir el LEEME.txt."); }
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            if (trabajando)
            {
                e.Cancel = true;
                if (!cerrarAlTerminar && Dialogo.Preguntar(this, "Se está creando una ISO. ¿Cancelar y salir? Lo que se creó hasta ahora se borra."))
                {
                    Cancelar = true;
                    cerrarAlTerminar = true;
                    Registrar("Cancelando...");
                }
                return;
            }
            animacion.Stop();
            if (musica != null) musica.Cerrar();
            base.OnFormClosing(e);
        }

        // Imágenes de la ventana sin mostrarla (--captura): trabajando, y esperando con un disco elegido.
        // Con ISO, la segunda imagen muestra cómo quedan elegidas (para probar la detección).
        public static bool Capturar(string path, List<string> isos)
        {
            using (var v = new Ventana(new string[0]))
            {
                v.ranuras[0] = new Ranura { Ruta = @"C:\Juegos\PS2\Xenosaga2UNDUB1.iso", Estado = "encurso" };
                v.trabajando = true;
                v.progreso = 47;
                v.tiempo = 0.35;
                v.sobre = Zona.Leeme;
                v.Registrar("Disco 1: comprobando los archivos...");
                v.Registrar("Disco 1: creando \"Xenosaga2UNDUB1 (Español).iso\"...");
                v.Guardar(path);
                v.ranuras[0].Estado = "original";
                v.ranuras[1] = new Ranura { Ruta = @"C:\Juegos\PS2\Otro juego.iso", Estado = "novalida" };
                v.trabajando = false;
                v.progreso = 0;
                v.tiempo = 0.5;
                v.sobre = Zona.Boton;
                v.Registrar("No es Xenosaga Episode II en versión americana (NTSC-U).");
                if (isos.Count > 0)
                {
                    v.ranuras[0] = new Ranura();
                    v.ranuras[1] = new Ranura();
                    foreach (string iso in isos) v.Asignar(iso, -1, false);
                }
                v.Guardar(Path.Combine(Path.GetDirectoryName(Path.GetFullPath(path)), Path.GetFileNameWithoutExtension(path) + "_espera.png"));
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
                g.DrawString("XS2·ES  //  CONFIRMAR", mono, cian, 10, 6, StringFormat.GenericTypographic);
            using (var blanco = new SolidBrush(Color.FromArgb(232, 238, 250)))
                g.DrawString(texto, letra, blanco, new RectangleF(18, 36, Ancho - 36, 64));
            g.Restore(estado);
            Boton(g, "si", si);
            Boton(g, "no", no);
        }

        void Boton(Graphics g, string nombre, Rectangle r)
        {
            string estado = apretado == nombre && sobre == nombre ? "presionado" : sobre == nombre ? "hover" : "normal";
            Dibujar(g, arte.Img[nombre + "_" + estado], r.X, r.Y);
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
