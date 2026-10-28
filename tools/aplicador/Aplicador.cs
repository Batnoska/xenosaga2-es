// Aplicador del parche de la traducción al español de Xenosaga Episode II (PS2, NTSC-U).
//
// Hace lo mismo que "python tools/parche.py aplicar" (con x2iso.build), pero en C# 5 para que
// funcione en cualquier Windows sin instalar nada: tools/kit.py lo compila con el csc que trae
// .NET Framework 4 y le incrusta el paquete (parche.zip). Si cambia la lógica de uno, hay que
// cambiar el otro; "python tools/kit.py VERSION --probar" comprueba que armen la misma ISO.
//
// Uso: abrirlo y elegir las ISO en la ventana (Ventana.cs), o arrastrarlas sobre el .exe.
//   Aplicar parche.exe [ISO...]                      la ventana, con esas ISO ya elegidas
//   Aplicar parche.exe --salida CARPETA ISO...       sin ventana (para las pruebas del kit)
//   Aplicar parche.exe --captura ARCHIVO.png [ISO...] guarda imágenes de la ventana (con esas ISO elegidas)
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Windows.Forms;

static partial class Aplicador
{
    const int SECTOR = 2048;
    static readonly Encoding Latin1 = Encoding.GetEncoding(28591);
    static readonly Dictionary<string, int> Discos = new Dictionary<string, int> { { "SLUS_208.92", 1 }, { "SLUS_211.33", 2 } };

    static long Sectors(long size) { return (size + SECTOR - 1) / SECTOR; }

    static string Sha1(byte[] data)
    {
        using (var h = SHA1.Create())
            return string.Concat(h.ComputeHash(data).Select(b => b.ToString("x2")));
    }

    static byte[] ReadAt(FileStream f, long offset, long count)
    {
        f.Seek(offset, SeekOrigin.Begin);
        var buf = new byte[count];
        int got = 0;
        while (got < count)
        {
            int n = f.Read(buf, got, (int)Math.Min(count - got, 1 << 24));
            if (n == 0) break;
            got += n;
        }
        if (got < count) Array.Resize(ref buf, got);
        return buf;
    }

    // ---- Lectura de la ISO (x2iso.Iso / Volume / parse_index) ----

    class IsoFile { public string Name; public long Lba, Size, Record; }

    class Iso : IDisposable
    {
        public readonly FileStream F;
        public readonly List<IsoFile> Files = new List<IsoFile>();  // en el orden del directorio
        public readonly Dictionary<string, IsoFile> ByName = new Dictionary<string, IsoFile>();
        public readonly string Executable;
        public readonly List<int> Groups;

        public Iso(string path)
        {
            F = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 1 << 16);
            byte[] pvd = ReadSectors(16, 1);
            if (pvd.Length < SECTOR || Latin1.GetString(pvd, 1, 5) != "CD001")
            {
                F.Dispose();
                throw new InvalidDataException("no es una imagen ISO de DVD");
            }
            long rootLba = BitConverter.ToUInt32(pvd, 158), rootLen = BitConverter.ToUInt32(pvd, 166);
            byte[] d = ReadSectors(rootLba, Sectors(rootLen));
            int p = 0;
            while (p < d.Length)
            {
                int n = d[p];
                if (n == 0)
                {
                    p = (p / SECTOR + 1) * SECTOR;
                    continue;
                }
                string name = Latin1.GetString(d, p + 33, d[p + 32]).Split(';')[0];
                if (name != "\0" && name != "\u0001")
                {
                    IsoFile f;
                    if (!ByName.TryGetValue(name, out f))
                    {
                        f = new IsoFile { Name = name };
                        ByName[name] = f;
                        Files.Add(f);
                    }
                    f.Lba = BitConverter.ToUInt32(d, p + 2);
                    f.Size = BitConverter.ToUInt32(d, p + 10);
                    f.Record = rootLba * SECTOR + p;
                }
                p += n;
            }
            Executable = Files.Select(f => f.Name).FirstOrDefault(n => n.StartsWith("SLUS_"));
            Groups = Files.Where(f => f.Name.StartsWith("XENOSAGA.") && f.Name.EndsWith("0"))
                          .Select(f => f.Name[f.Name.Length - 2] - '0').OrderBy(g => g).ToList();
        }

        public byte[] ReadSectors(long lba, long count) { return ReadAt(F, lba * SECTOR, count * SECTOR); }

        public byte[] ReadFile(string name)
        {
            IsoFile f = ByName[name];
            return ReadAt(F, f.Lba * SECTOR, f.Size);
        }

        public void Dispose() { F.Dispose(); }
    }

    class Entry { public string Path; public long Sector, Size; public int FieldPos; }

    // Rebanada al estilo de Python: a[start:stop], con índices negativos y recortados.
    static byte[] Slice(byte[] a, int start, int stop)
    {
        int n = a.Length;
        start = start < 0 ? Math.Max(0, n + start) : Math.Min(start, n);
        stop = stop < 0 ? Math.Max(0, n + stop) : Math.Min(stop, n);
        if (stop <= start) return new byte[0];
        var r = new byte[stop - start];
        Array.Copy(a, start, r, 0, r.Length);
        return r;
    }

    static byte[] UntilZero(byte[] a)
    {
        int i = Array.IndexOf(a, (byte)0);
        return i < 0 ? a : Slice(a, 0, i);
    }

    static byte[] ApplyName(byte[] reference, int P, byte[] stored)
    {
        if (P == 0) return UntilZero(stored);
        int start = reference.Length - ((P >> 4) + 1);
        byte[] head = Slice(reference, 0, start), tail = Slice(reference, start + stored.Length, int.MaxValue);
        return UntilZero(head.Concat(stored).Concat(tail).ToArray());
    }

    static List<Entry> ParseIndex(byte[] data)
    {
        var entries = new List<Entry>();
        var stack = new List<byte[]>();
        byte[] prevFile = new byte[0];
        int pos = 1;
        while (pos < data.Length)
        {
            int L = data[pos];
            if (L == 0) break;
            int n = L & 0x3F;
            if ((L & 0x80) != 0)
            {
                int up = data[pos + 1], P = data[pos + 2];
                int depth = stack.Count - up;
                int keep = depth < 0 ? Math.Max(0, stack.Count + depth) : Math.Min(depth, stack.Count);
                byte[] reference = up != 0 ? stack[depth < 0 ? stack.Count + depth : depth] : new byte[0];
                byte[] folder = ApplyName(reference, P, Slice(data, pos + 3, pos + n));
                stack = stack.Take(keep).ToList();
                stack.Add(folder);
                pos += n;
                continue;
            }
            byte[] name = ApplyName(prevFile, data[pos + 1], Slice(data, pos + 2, pos + n));
            prevFile = name;
            pos += n;
            var e = new Entry
            {
                Sector = data[pos] | data[pos + 1] << 8 | data[pos + 2] << 16,
                Size = BitConverter.ToUInt32(data, pos + 3),
                FieldPos = pos,
                Path = string.Join("/", stack.Concat(new[] { name }).Select(s => Latin1.GetString(s))),
            };
            entries.Add(e);
            pos += (L & 0x40) != 0 ? 10 : 7;
        }
        return entries;
    }

    class Volume
    {
        public readonly Iso Iso;
        public readonly string IndexName, DataName;
        public readonly long Base;
        public readonly byte[] Index;
        public readonly Dictionary<string, Entry> ByPath = new Dictionary<string, Entry>();

        public Volume(Iso iso, int group)
        {
            Iso = iso;
            IndexName = "XENOSAGA." + group + "0";
            DataName = "XENOSAGA." + group + "1";
            Base = iso.ByName[IndexName].Lba;
            if (iso.ByName[DataName].Lba != Base + Sectors(iso.ByName[IndexName].Size))
                throw new InvalidDataException("el volumen " + group + " no tiene el formato esperado");
            Index = iso.ReadFile(IndexName);
            foreach (Entry e in ParseIndex(Index))
                ByPath[e.Path] = e;
        }

        public byte[] Read(Entry e) { return ReadAt(Iso.F, (Base + e.Sector) * SECTOR, e.Size); }
    }

    // ---- Reconstrucción (x2iso.build) ----

    static bool IsData(string name) { return name.StartsWith("XENOSAGA.") && name.EndsWith("1"); }

    static void SetBothEndian(byte[] buf, int off, long value)
    {
        byte[] le = BitConverter.GetBytes((uint)value);
        Array.Copy(le, 0, buf, off, 4);
        for (int i = 0; i < 4; i++) buf[off + 4 + i] = le[3 - i];
    }

    // replacements: grupo -> (ruta -> datos); loose: archivos de la raíz, del mismo tamaño.
    static void Build(string isoPath, string outPath, Dictionary<int, SortedDictionary<string, byte[]>> replacements,
                      Dictionary<string, byte[]> loose, Action<long, long> progress)
    {
        using (var iso = new Iso(isoPath))
        {
            var volumes = iso.Groups.ToDictionary(g => g, g => new Volume(iso, g));
            var inPlace = new Dictionary<long, byte[]>();
            var room = new Dictionary<long, long>();
            var appended = new Dictionary<int, List<byte[]>>();
            var newIndex = new Dictionary<int, byte[]>();
            foreach (int g in iso.Groups)
            {
                Volume vol = volumes[g];
                byte[] index = (byte[])vol.Index.Clone();
                long end = Sectors(iso.ByName[vol.IndexName].Size) + Sectors(iso.ByName[vol.DataName].Size);
                var tail = new List<byte[]>();
                SortedDictionary<string, byte[]> files;
                if (replacements.TryGetValue(g, out files))
                {
                    foreach (var kv in files)
                    {
                        Entry e = vol.ByPath[kv.Key];
                        byte[] data = kv.Value;
                        long sector;
                        if (Sectors(data.Length) <= Sectors(e.Size))
                        {
                            long offset = (vol.Base + e.Sector) * SECTOR;
                            inPlace[offset] = data;
                            room[offset] = Sectors(e.Size) * SECTOR;
                            sector = e.Sector;
                        }
                        else
                        {
                            sector = end;
                            tail.Add(data);
                            end += Sectors(data.Length);
                        }
                        index[e.FieldPos] = (byte)sector;
                        index[e.FieldPos + 1] = (byte)(sector >> 8);
                        index[e.FieldPos + 2] = (byte)(sector >> 16);
                        Array.Copy(BitConverter.GetBytes((uint)data.Length), 0, index, e.FieldPos + 3, 4);
                    }
                }
                newIndex[g] = index;
                appended[g] = tail;
            }
            foreach (var kv in loose)
            {
                IsoFile f = iso.ByName[kv.Key];
                if (kv.Value.Length != f.Size) throw new InvalidDataException(kv.Key + ": el tamaño debe quedar igual");
                inPlace[f.Lba * SECTOR] = kv.Value;
                room[f.Lba * SECTOR] = Sectors(f.Size) * SECTOR;
            }

            // Registros ISO9660 nuevos: cada parte de datos crece y lo que sigue se corre.
            var grow = volumes.Keys.ToDictionary(g => g, g => appended[g].Sum(d => Sectors(d.Length)));
            List<IsoFile> layout = iso.Files.OrderBy(f => f.Lba).ToList();  // OrderBy es estable, como sorted()
            long shift = 0;
            var newLba = new Dictionary<string, long>();
            var newSize = new Dictionary<string, long>();
            foreach (IsoFile f in layout)
            {
                newLba[f.Name] = f.Lba + shift;
                newSize[f.Name] = f.Size;
                if (IsData(f.Name))
                {
                    int g = f.Name[f.Name.Length - 2] - '0';
                    newSize[f.Name] = f.Size + grow[g] * SECTOR;
                    shift += grow[g];
                }
            }
            long totalSectors = BitConverter.ToUInt32(iso.ReadSectors(16, 1), 80) + shift;
            long total = iso.F.Length + shift * SECTOR, written = 0;

            using (var outFile = new FileStream(outPath, FileMode.Create, FileAccess.ReadWrite, FileShare.None, 1 << 16))
            {
                var buffer = new byte[16 << 20];
                Action<long, long> copy = (start, stop) =>
                {
                    iso.F.Seek(start, SeekOrigin.Begin);
                    long remaining = stop - start;
                    while (remaining > 0)
                    {
                        int n = iso.F.Read(buffer, 0, (int)Math.Min(remaining, buffer.Length));
                        if (n == 0) break;
                        outFile.Write(buffer, 0, n);
                        remaining -= n;
                        written += n;
                        progress(written, total);
                    }
                };
                long cursor = 0;
                foreach (IsoFile f in layout)
                {
                    if (!IsData(f.Name)) continue;
                    int g = f.Name[f.Name.Length - 2] - '0';
                    long stop = (f.Lba + Sectors(f.Size)) * SECTOR;
                    copy(cursor, stop);
                    foreach (byte[] data in appended[g])
                    {
                        outFile.Write(data, 0, data.Length);
                        long pad = Sectors(data.Length) * SECTOR - data.Length;
                        outFile.Write(new byte[pad], 0, (int)pad);
                        written += data.Length + pad;
                    }
                    cursor = stop;
                }
                copy(cursor, iso.F.Length);

                // Reemplazos en el lugar (en coordenadas de la ISO original, corridas).
                foreach (var kv in inPlace)
                {
                    long lba = kv.Key / SECTOR, extra = 0;
                    foreach (IsoFile f in layout)
                        if (IsData(f.Name) && lba >= f.Lba + Sectors(f.Size))
                            extra += grow[f.Name[f.Name.Length - 2] - '0'];
                    outFile.Seek(kv.Key + extra * SECTOR, SeekOrigin.Begin);
                    outFile.Write(kv.Value, 0, kv.Value.Length);
                    long pad = room[kv.Key] - kv.Value.Length;
                    outFile.Write(new byte[pad], 0, (int)pad);
                }
                foreach (var kv in newIndex)
                {
                    outFile.Seek(newLba[volumes[kv.Key].IndexName] * SECTOR, SeekOrigin.Begin);
                    outFile.Write(kv.Value, 0, kv.Value.Length);
                }
                foreach (IsoFile f in iso.Files)
                {
                    var record = new byte[34];
                    outFile.Seek(f.Record, SeekOrigin.Begin);
                    outFile.Read(record, 0, 34);
                    SetBothEndian(record, 2, newLba[f.Name]);
                    SetBothEndian(record, 10, newSize[f.Name]);
                    outFile.Seek(f.Record, SeekOrigin.Begin);
                    outFile.Write(record, 0, 34);
                }
                foreach (long lba in new long[] { 16, 17 })  // descriptor primario (y el siguiente, si es suplementario)
                {
                    var head = new byte[6];
                    outFile.Seek(lba * SECTOR, SeekOrigin.Begin);
                    outFile.Read(head, 0, 6);
                    if ((head[0] == 1 || head[0] == 2) && Latin1.GetString(head, 1, 5) == "CD001")
                    {
                        var value = new byte[8];
                        SetBothEndian(value, 0, totalSectors);
                        outFile.Seek(lba * SECTOR + 80, SeekOrigin.Begin);
                        outFile.Write(value, 0, 8);
                    }
                }
            }
        }
    }

    // ---- Paquete y aplicación (parche.aplicar) ----

    class PatchEntry { public string Group, Path, Original, New, Stored; }

    static ZipArchive OpenPackage(out Dictionary<string, List<PatchEntry>> manifest)
    {
        Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream("parche.zip");
        if (s == null) throw new InvalidDataException("al programa le falta el paquete de la traducción");
        var zip = new ZipArchive(s, ZipArchiveMode.Read);
        manifest = new Dictionary<string, List<PatchEntry>>();
        using (var reader = new StreamReader(zip.GetEntry("manifest.tsv").Open(), Encoding.UTF8))
        {
            string line;
            while ((line = reader.ReadLine()) != null)
            {
                string[] c = line.Split('\t');
                if (c.Length != 6) continue;
                List<PatchEntry> list;
                if (!manifest.TryGetValue(c[0], out list)) manifest[c[0]] = list = new List<PatchEntry>();
                list.Add(new PatchEntry { Group = c[1], Path = c[2], Original = c[3], New = c[4], Stored = c[5] });
            }
        }
        return zip;
    }

    static byte[] ReadEntry(ZipArchive zip, string name)
    {
        using (Stream s = zip.GetEntry(name).Open())
        using (var m = new MemoryStream())
        {
            s.CopyTo(m);
            return m.ToArray();
        }
    }

    // Arma el archivo traducido a partir del original y sus diferencias (parche.undelta):
    // 0, u32 posición, u32 largo = copiar del original; 1, u32 largo, bytes = agregar.
    static byte[] Undelta(byte[] src, byte[] ops)
    {
        var result = new MemoryStream();
        int pos = 0;
        while (pos < ops.Length)
        {
            if (ops[pos] == 0)
            {
                result.Write(src, BitConverter.ToInt32(ops, pos + 1), BitConverter.ToInt32(ops, pos + 5));
                pos += 9;
            }
            else
            {
                int length = BitConverter.ToInt32(ops, pos + 1);
                result.Write(ops, pos + 5, length);
                pos += 5 + length;
            }
        }
        return result.ToArray();
    }

    // El archivo actual de la ISO para una entrada del paquete (vacío si no está).
    static byte[] Current(Iso iso, Dictionary<int, Volume> volumes, PatchEntry e)
    {
        if (e.Group == "raiz")
            return iso.ByName.ContainsKey(e.Path) ? iso.ReadFile(e.Path) : new byte[0];
        Volume vol;
        Entry entry;
        if (volumes.TryGetValue(int.Parse(e.Group), out vol) && vol.ByPath.TryGetValue(e.Path, out entry))
            return vol.Read(entry);
        return new byte[0];
    }

    static string Gb(long bytes) { return (bytes / (1024.0 * 1024 * 1024)).ToString("0.0"); }

    // Lo que cuenta Process mientras trabaja: la consola lo escribe y la ventana lo muestra.
    interface IAviso
    {
        void Linea(string texto);
        void Detalle(string texto);       // la lista de archivos que no coinciden
        void Avance(int porcentaje);      // de la ISO actual; para cancelar, tira OperationCanceledException
        bool Confirmar(string pregunta);
    }

    enum Resultado { Lista, YaTraducida, Error }

    // Una ISO parcheada con otra versión de la traducción: el ejecutable es el nuevo (casi nunca
    // cambia entre versiones) pero otros archivos no. Hay que partir de la ISO original.
    const string Anterior = "Disco {0}: tiene una versión anterior de la traducción.\nAplica el parche sobre tu ISO original.";

    // Mirada rápida a una ISO al elegirla: qué disco es y si el ejecutable es el original, el
    // traducido u otro. La comprobación completa la hace Process.
    static string Detectar(string isoPath, Dictionary<string, List<PatchEntry>> manifest, out int disc, out string estado)
    {
        disc = 0;
        estado = "novalida";
        try
        {
            using (var iso = new Iso(isoPath))
            {
                List<PatchEntry> entries;
                if (iso.Executable == null || !manifest.TryGetValue(iso.Executable, out entries))
                    return "No es Xenosaga Episode II en versión americana (NTSC-U).";
                disc = Discos[iso.Executable];
                string exe = iso.Executable;
                PatchEntry e = entries.First(x => x.Group == "raiz" && x.Path == exe);
                string sha = Sha1(iso.ReadFile(exe));
                if (sha == e.New)
                {
                    var volumes = iso.Groups.ToDictionary(g => g, g => new Volume(iso, g));
                    if (entries.Any(x => Sha1(Current(iso, volumes, x)) != x.New))
                    {
                        estado = "anterior";
                        return string.Format(Anterior, disc);
                    }
                    estado = "traducida";
                    return string.Format("Disco {0}: esta ISO ya tiene la traducción.", disc);
                }
                if (sha != e.Original)
                {
                    estado = "distinta";
                    return string.Format("Disco {0}: no es la versión original (¿otro parche?).", disc);
                }
                estado = "original";
                return string.Format("Disco {0}: listo para aplicar el parche.", disc);
            }
        }
        catch (InvalidDataException ex) { return "No se puede usar: " + ex.Message + "."; }
        catch (IOException ex) { return "No se puede abrir: " + ex.Message; }
        catch (UnauthorizedAccessException ex) { return "No se puede abrir: " + ex.Message; }
    }

    // El avance de una ISO: 0-10 % comprobar, 10-95 % crear y 95-100 % verificar.
    static Resultado Process(string isoPath, string outDir, ZipArchive zip, Dictionary<string, List<PatchEntry>> manifest, IAviso aviso)
    {
        if (!File.Exists(isoPath))
        {
            aviso.Linea("No se encuentra el archivo.");
            return Resultado.Error;
        }
        var replacements = new Dictionary<int, SortedDictionary<string, byte[]>>();
        var loose = new Dictionary<string, byte[]>();
        List<PatchEntry> entries;
        int disc;
        try
        {
            using (var iso = new Iso(isoPath))
            {
                if (iso.Executable == null || !manifest.TryGetValue(iso.Executable, out entries))
                {
                    aviso.Linea("No es Xenosaga Episode II en versión americana (NTSC-U).");
                    return Resultado.Error;
                }
                disc = Discos[iso.Executable];
                aviso.Linea(string.Format("Disco {0}: comprobando los archivos...", disc));
                var volumes = iso.Groups.ToDictionary(g => g, g => new Volume(iso, g));
                var bad = new List<string>();
                bool exeTraducido = false;
                for (int i = 0; i < entries.Count; i++)
                {
                    PatchEntry e = entries[i];
                    aviso.Avance(i * 10 / entries.Count);
                    byte[] current = Current(iso, volumes, e);
                    string sha = Sha1(current);
                    if (e.Group == "raiz" && e.Path == iso.Executable) exeTraducido = sha == e.New;
                    if (sha == e.New) continue;  // ya está traducido
                    if (sha != e.Original)
                    {
                        bad.Add(e.Path);
                        continue;
                    }
                    byte[] data = Undelta(current, ReadEntry(zip, e.Stored));
                    if (Sha1(data) != e.New) throw new InvalidDataException("el paquete está dañado (" + e.Stored + ")");
                    if (e.Group == "raiz")
                        loose[e.Path] = data;
                    else
                    {
                        int g = int.Parse(e.Group);
                        if (!replacements.ContainsKey(g)) replacements[g] = new SortedDictionary<string, byte[]>(StringComparer.Ordinal);
                        replacements[g][e.Path] = data;
                    }
                }
                if (bad.Count > 0 && exeTraducido)
                {
                    foreach (string linea in string.Format(Anterior, disc).Split('\n')) aviso.Linea(linea);
                    return Resultado.Error;
                }
                if (bad.Count > 0)
                {
                    aviso.Linea(string.Format("Disco {0}: {1} archivos no son los originales. No se tocó nada.", disc, bad.Count));
                    foreach (string b in bad.Take(10)) aviso.Detalle(b);
                    if (bad.Count > 10) aviso.Detalle(string.Format("... y {0} más", bad.Count - 10));
                    aviso.Linea("¿Es otra versión o una ISO con otro parche?");
                    return Resultado.Error;
                }
            }
        }
        catch (InvalidDataException ex)
        {
            aviso.Linea("No se puede usar: " + ex.Message + ".");
            return Resultado.Error;
        }
        int count = loose.Count + replacements.Values.Sum(r => r.Count);
        if (count == 0)
        {
            aviso.Linea(string.Format("Disco {0}: esta ISO ya tiene la traducción.", disc));
            return Resultado.YaTraducida;
        }

        string name = Path.GetFileNameWithoutExtension(isoPath) + " (Español).iso";
        string outPath = Path.Combine(outDir ?? Path.GetDirectoryName(Path.GetFullPath(isoPath)), name);
        if (File.Exists(outPath) && !aviso.Confirmar(string.Format("Ya existe \"{0}\". ¿Reemplazarlo?", name)))
        {
            aviso.Linea("No se tocó nada.");
            return Resultado.Error;
        }
        long needed = new FileInfo(isoPath).Length + 64L * 1024 * 1024;
        try
        {
            var drive = new DriveInfo(Path.GetPathRoot(Path.GetFullPath(outPath)));
            if (drive.AvailableFreeSpace < needed)
            {
                aviso.Linea(string.Format("Falta espacio: hacen falta {0} GB libres en {1}.", Gb(needed), drive.Name));
                return Resultado.Error;
            }
        }
        catch (ArgumentException) { }  // unidad de red: se intenta igual

        aviso.Linea(string.Format("Disco {0}: creando \"{1}\"...", disc, name));
        try
        {
            Build(isoPath, outPath, replacements, loose, (done, total) => aviso.Avance(10 + (int)(done * 85 / total)));
            aviso.Linea(string.Format("Disco {0}: verificando...", disc));
            using (var result = new Iso(outPath))
            {
                var volumes = result.Groups.ToDictionary(g => g, g => new Volume(result, g));
                for (int i = 0; i < entries.Count; i++)
                {
                    aviso.Avance(95 + i * 5 / entries.Count);
                    if (Sha1(Current(result, volumes, entries[i])) != entries[i].New)
                        throw new InvalidDataException("la ISO creada no coincide con la esperada");
                }
            }
        }
        catch (Exception ex)
        {
            try { File.Delete(outPath); } catch (IOException) { }
            if (ex is OperationCanceledException) throw;
            aviso.Linea("Error: " + ex.Message);
            return Resultado.Error;
        }
        aviso.Avance(100);
        aviso.Linea(string.Format("Listo: disco {0} traducido ({1} archivos).", disc, count));
        return Resultado.Lista;
    }

    class AvisoConsola : IAviso
    {
        int last = -1;

        public void Linea(string texto)
        {
            if (last >= 0) Console.WriteLine();
            last = -1;
            Console.WriteLine("  " + texto);
        }

        public void Detalle(string texto) { Linea("  " + texto); }

        public void Avance(int porcentaje)
        {
            if (porcentaje != last) Console.Write("\r  {0,3}%", last = porcentaje);
        }

        public bool Confirmar(string pregunta)
        {
            Linea(pregunta + " (s/n): ");
            string answer = Console.ReadLine();
            return answer != null && answer.Trim().StartsWith("s", StringComparison.OrdinalIgnoreCase);
        }
    }

    [STAThread]
    static int Main(string[] args)
    {
        string outDir = null, captura = null;
        bool consola = false;
        var isos = new List<string>();
        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--salida" && i + 1 < args.Length) { outDir = args[++i]; consola = true; }
            else if (args[i] == "--consola") consola = true;
            else if (args[i] == "--captura" && i + 1 < args.Length) captura = args[++i];
            else isos.Add(args[i]);
        }
        if (consola) return Consola(isos, outDir);
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        if (captura != null) return Ventana.Capturar(captura, isos) ? 0 : 1;
        Application.Run(new Ventana(isos));
        return 0;
    }

    // Modo sin ventana, para las pruebas de tools/kit.py: escribe en la salida estándar.
    static int Consola(List<string> isos, string outDir)
    {
        var output = new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false)) { AutoFlush = true };
        Console.SetOut(output);
        Console.WriteLine("Xenosaga Episode II en español - versión " + Version);
        bool ok = true;
        try
        {
            Dictionary<string, List<PatchEntry>> manifest;
            using (ZipArchive zip = OpenPackage(out manifest))
            {
                foreach (string iso in isos)
                {
                    Console.WriteLine();
                    Console.WriteLine(Path.GetFileName(iso));
                    ok &= Process(iso, outDir, zip, manifest, new AvisoConsola()) != Resultado.Error;
                }
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine("Error inesperado: " + ex.Message);
            ok = false;
        }
        Console.WriteLine();
        Console.WriteLine(ok ? "Terminado." : "Terminado con problemas.");
        return ok ? 0 : 1;
    }
}
