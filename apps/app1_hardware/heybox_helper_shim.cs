using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;

// 小黑盒桌面版硬件采集 helper 的运行时拦截器（C# 5 兼容）。
// IFEO 将本程序作为 hardware-windows-helper.exe 的“调试器”启动：
//   HeyboxHelperShim.exe <原始helper路径> <原始参数...>
// 本程序改为运行同目录的 helper_real.exe（避免再次触发 IFEO），
// 拿到 stdout JSON 后按 ToolboxMaster 配置改写硬件字段，再输出给小黑盒。
internal static class Program
{
    private static readonly string[] ConfigCandidates = BuildConfigCandidates();

    private static string[] BuildConfigCandidates()
    {
        var list = new List<string>();
        string appData = Environment.GetEnvironmentVariable("APPDATA");
        string localAppData = Environment.GetEnvironmentVariable("LOCALAPPDATA");
        if (!string.IsNullOrEmpty(appData))
            list.Add(Path.Combine(appData, "ToolboxMaster", "config", "app1_hardware", "config.json"));
        if (!string.IsNullOrEmpty(localAppData))
            list.Add(Path.Combine(localAppData, "ToolboxMaster", "config", "app1_hardware", "config.json"));
        list.Add(@"C:\Users\Public\Hardware_Config.json");
        list.Add(@"C:\ToolboxData\config\app1_hardware\config.json");
        string pf = Environment.GetEnvironmentVariable("ProgramFiles");
        string pf86 = Environment.GetEnvironmentVariable("ProgramFiles(x86)");
        if (!string.IsNullOrEmpty(pf)) list.Add(Path.Combine(pf, "DMBOX", "apps", "app1_hardware", "config.json"));
        if (!string.IsNullOrEmpty(pf86)) list.Add(Path.Combine(pf86, "DMBOX", "apps", "app1_hardware", "config.json"));
        list.Add(@"D:\AI\整合包\apps\app1_hardware\config.json");
        return list.ToArray();
    }

    private static Dictionary<string, object> LoadTarget()
    {
        foreach (string p in ConfigCandidates)
        {
            try
            {
                if (!File.Exists(p)) continue;
                var ser = new JavaScriptSerializer();
                ser.MaxJsonLength = int.MaxValue;
                var root = ser.Deserialize<Dictionary<string, object>>(File.ReadAllText(p, Encoding.UTF8));
                if (root == null) continue;
                object ctObj;
                if (root.TryGetValue("custom_target", out ctObj))
                {
                    var ct = ctObj as Dictionary<string, object>;
                    if (ct != null) return ct;
                }
            }
            catch { }
        }
        return null;
    }

    private static string S(Dictionary<string, object> d, string k)
    {
        if (d == null) return null;
        object v;
        if (!d.TryGetValue(k, out v) || v == null) return null;
        string s = Convert.ToString(v, CultureInfo.InvariantCulture);
        if (string.IsNullOrEmpty(s) || s.Trim().Length == 0) return null;
        return s.Trim();
    }

    private static double? N(Dictionary<string, object> d, string k)
    {
        if (d == null) return null;
        object v;
        if (!d.TryGetValue(k, out v) || v == null) return null;
        try
        {
            double x = Convert.ToDouble(v, CultureInfo.InvariantCulture);
            if (x > 0) return x;
            return null;
        }
        catch { return null; }
    }

    private static long? Bytes(double? gb)
    {
        if (!gb.HasValue) return null;
        return (long)Math.Round(gb.Value * 1024.0 * 1024.0 * 1024.0);
    }

    private static bool IsVirtualGpu(string name)
    {
        if (string.IsNullOrEmpty(name)) return true;
        string n = name.ToLowerInvariant();
        string[] bad = { "virtual", "gameviewer", "oray", "parsec", "spacedesk", "sunlogin", "mumu", "basic render", "remote", "mirror", "idd" };
        foreach (string b in bad) if (n.Contains(b)) return true;
        return false;
    }

    private static void Set(Dictionary<string, object> d, string k, object v)
    {
        if (d != null && v != null) d[k] = v;
    }

    private static object Apply(object node, Dictionary<string, object> cfg)
    {
        var root = node as Dictionary<string, object>;
        if (root == null || cfg == null) return node;

        object tmp;
        if (root.TryGetValue("cpu", out tmp))
        {
            var cpu = tmp as Dictionary<string, object>;
            Set(cpu, "name", S(cfg, "cpu_model"));
        }

        long? total = Bytes(N(cfg, "memory_size_gb"));
        string memVendor = S(cfg, "memory_vendor");
        string memPn = S(cfg, "memory_part_number");
        double? memClock = N(cfg, "memory_clock_mhz");
        string memType = S(cfg, "memory_type");

        ApplyModules(root, "memory", "modules", total, memVendor, memPn, memClock, memType, false);
        ApplyModules(root, "smbiosMemory", null, total, memVendor, memPn, memClock, memType, true);

        long? vram = Bytes(N(cfg, "gpu_vram_gb"));
        string gpuModel = S(cfg, "gpu_model");
        if (root.TryGetValue("gpus", out tmp) && gpuModel != null)
        {
            var gpus = tmp as object[];
            if (gpus != null)
            {
                bool done = false;
                for (int i = 0; i < gpus.Length; i++)
                {
                    var g = gpus[i] as Dictionary<string, object>;
                    if (g == null) continue;
                    object nameObj;
                    g.TryGetValue("name", out nameObj);
                    string gname = Convert.ToString(nameObj);
                    if (!done && !IsVirtualGpu(gname))
                    {
                        g["name"] = gpuModel;
                        if (vram.HasValue) g["memoryBytes"] = vram.Value;
                        done = true;
                    }
                }
            }
        }

        if (root.TryGetValue("board", out tmp))
        {
            var board = tmp as Dictionary<string, object>;
            Set(board, "name", S(cfg, "motherboard_product"));
            Set(board, "product", S(cfg, "motherboard_product"));
            Set(board, "vendor", S(cfg, "motherboard_vendor"));
        }
        if (root.TryGetValue("computer", out tmp))
        {
            var comp = tmp as Dictionary<string, object>;
            Set(comp, "model", S(cfg, "motherboard_product"));
        }

        string diskModel = S(cfg, "disk_model");
        if (root.TryGetValue("disks", out tmp) && diskModel != null)
        {
            var disks = tmp as object[];
            if (disks != null && disks.Length > 0)
            {
                var disk = disks[0] as Dictionary<string, object>;
                if (disk != null)
                {
                    disk["name"] = diskModel;
                    long? sz = DiskBytes(diskModel);
                    if (sz.HasValue) disk["sizeBytes"] = sz.Value;
                }
            }
        }
        return root;
    }

    private static long? DiskBytes(string model)
    {
        if (string.IsNullOrEmpty(model)) return null;
        var m = Regex.Match(model, @"(\d+(?:\.\d+)?)\s*TB", RegexOptions.IgnoreCase);
        if (m.Success) return (long)Math.Round(double.Parse(m.Groups[1].Value, CultureInfo.InvariantCulture) * Math.Pow(1024, 4));
        m = Regex.Match(model, @"(\d+(?:\.\d+)?)\s*GB", RegexOptions.IgnoreCase);
        if (m.Success) return (long)Math.Round(double.Parse(m.Groups[1].Value, CultureInfo.InvariantCulture) * Math.Pow(1024, 3));
        return null;
    }

    private static void ApplyModules(Dictionary<string, object> root, string arrKey, string nestedKey,
        long? total, string vendor, string partNumber, double? clock, string type, bool smbios)
    {
        object[] arr = null;
        object tmp;
        if (nestedKey != null)
        {
            if (root.TryGetValue(arrKey, out tmp))
            {
                var mem = tmp as Dictionary<string, object>;
                if (mem != null && mem.TryGetValue(nestedKey, out tmp)) arr = tmp as object[];
            }
        }
        else if (root.TryGetValue(arrKey, out tmp)) arr = tmp as object[];
        if (arr == null || arr.Length == 0) return;

        long per = 0; long last = 0;
        if (total.HasValue)
        {
            per = total.Value / arr.Length;
            last = total.Value - per * (arr.Length - 1);
        }

        for (int i = 0; i < arr.Length; i++)
        {
            var m = arr[i] as Dictionary<string, object>;
            if (m == null) continue;
            if (total.HasValue) m["sizeBytes"] = (i == arr.Length - 1 ? last : per);
            if (vendor != null) m["vendor"] = vendor;
            if (partNumber != null) m["partNumber"] = partNumber;
            if (clock.HasValue) m["speedMhz"] = (long)Math.Round(clock.Value);
            if (type != null)
            {
                m["type"] = type;
                if (smbios) m["memoryType"] = type;
            }
        }
    }

    private static string Quote(string s)
    {
        if (s == null) return "\"\"";
        return "\"" + s.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
    }

    private static int Main(string[] args)
    {
        try { Console.OutputEncoding = new UTF8Encoding(false); } catch { }
        string baseDir = AppDomain.CurrentDomain.BaseDirectory;
        string real = Path.Combine(baseDir, "helper_real.exe");
        if (!File.Exists(real))
        {
            Console.Error.WriteLine("TBX shim: helper_real.exe not found in " + baseDir);
            return 3;
        }

        var psi = new ProcessStartInfo(real);
        psi.UseShellExecute = false;
        psi.RedirectStandardOutput = true;
        psi.RedirectStandardError = true;
        psi.CreateNoWindow = true;
        psi.WorkingDirectory = baseDir;
        psi.StandardOutputEncoding = new UTF8Encoding(false);
        psi.StandardErrorEncoding = new UTF8Encoding(false);

        // IFEO 传入：args[0] 为原始 helper 路径，其余才是真正的命令参数
        var sb = new StringBuilder();
        for (int i = 1; i < args.Length; i++)
        {
            if (sb.Length > 0) sb.Append(' ');
            sb.Append(Quote(args[i]));
        }
        psi.Arguments = sb.ToString();

        string stdout = "";
        string stderr = "";
        int exit = 1;
        try
        {
            var p = Process.Start(psi);
            stdout = p.StandardOutput.ReadToEnd();
            stderr = p.StandardError.ReadToEnd();
            p.WaitForExit();
            exit = p.ExitCode;
            p.Dispose();
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("TBX shim: " + ex.Message);
            return 4;
        }

        string output = stdout;
        if (!string.IsNullOrEmpty(stdout) && stdout.TrimStart().StartsWith("{"))
        {
            try
            {
                var ser = new JavaScriptSerializer();
                ser.MaxJsonLength = int.MaxValue;
                object obj = ser.Deserialize<object>(stdout);
                var cfg = LoadTarget();
                if (cfg != null) obj = Apply(obj, cfg);
                output = ser.Serialize(obj);
            }
            catch { output = stdout; }
        }

        Console.Write(output);
        if (!string.IsNullOrEmpty(stderr)) Console.Error.Write(stderr);
        return exit;
    }
}
