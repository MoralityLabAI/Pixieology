param(
    [ValidateSet("smoke", "action-train", "prose-train", "prose-exact-train", "faebench")]
    [string]$Mode = "smoke",
    [ValidateSet("0.8B", "1.7B")]
    [string]$ModelSize = "0.8B",
    [string]$DataRoot = "",
    [string]$ModelCacheDir = "",
    [string]$HFHome = "",
    [string]$PythonBin = "python",
    [string]$OutputTag = "",
    [string]$AdapterPath = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSCommandPath
$Config = Get-Content -Raw (Join-Path $RepoRoot "pixieology.config.json") | ConvertFrom-Json

function Resolve-ConfigPath {
    param([string]$Value)
    if ([System.IO.Path]::IsPathRooted($Value)) { return $Value }
    return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Value))
}

if (-not $DataRoot) {
    $DataRoot = Resolve-ConfigPath $Config.paths.data_root
}
if (-not $ModelCacheDir) {
    $ModelCacheDir = Resolve-ConfigPath $Config.paths.model_cache_dir
}

if (-not $HFHome) {
    $HFHome = Resolve-ConfigPath $Config.paths.hf_home
}

$env:PIXIE_ROOT = $RepoRoot
$env:PIXIE_DATA_ROOT = $DataRoot
$env:PIXIE_MODEL_CACHE_DIR = $ModelCacheDir
$env:HF_HOME = $HFHome
$env:HUGGINGFACE_HUB_CACHE = $HFHome
$env:HF_HUB_CACHE = $HFHome

$dirs = @(
    $DataRoot,
    $ModelCacheDir,
    $HFHome,
    (Join-Path $DataRoot "normalized_trajectories"),
    (Join-Path $DataRoot "pixie_research")
)
foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

function Invoke-LocalPython {
    param([string[]]$PythonArgs)
    & $PythonBin @PythonArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $PythonBin $($PythonArgs -join ' ')"
    }
}

function Default-Tag {
    param([string]$Prefix)
    if ($OutputTag) {
        return $OutputTag
    }
    return "$Prefix-$(Get-Date -Format yyyy-MM-dd_HHmmss)"
}

function ModelSize-Slug {
    param([string]$Value)
    return $Value.Replace(".", "p").ToLowerInvariant()
}

function Storyworld-Local4GBArgs {
    param(
        [string]$Tag,
        [string]$SelectedModel
    )

    $args = @(
        ".\run_pixie_storyworld_sft.py",
        "--models", $SelectedModel,
        "--skip-bridge",
        "--data-root", $DataRoot,
        "--output-root", (Join-Path $DataRoot "pixie_research\$Tag")
    )

    switch ($SelectedModel) {
        "0.8B" {
            $args += @(
                "--batch-size", "1",
                "--grad-accum", "8",
                "--lora-r", "4",
                "--lora-alpha", "8",
                "--max-memory-mib", "3300",
                "--max-len", "320",
                "--max-records", "96",
                "--action-max-len", "256",
                "--action-max-records", "160",
                "--action-steps", "80",
                "--prose-max-len", "256",
                "--prose-max-records", "160",
                "--prose-steps", "96",
                "--prose-exact-max-len", "256",
                "--prose-exact-max-records", "96",
                "--prose-exact-steps", "64"
            )
        }
        "1.7B" {
            $args += @(
                "--batch-size", "1",
                "--grad-accum", "16",
                "--lora-r", "2",
                "--lora-alpha", "4",
                "--max-memory-mib", "3900",
                "--device-map", "single-gpu",
                "--max-len", "224",
                "--max-records", "48",
                "--action-max-len", "192",
                "--action-max-records", "96",
                "--action-steps", "48",
                "--prose-max-len", "192",
                "--prose-max-records", "96",
                "--prose-steps", "64",
                "--prose-exact-max-len", "192",
                "--prose-exact-max-records", "64",
                "--prose-exact-steps", "48"
            )
        }
    }

    return $args
}

Push-Location $RepoRoot
try {
    switch ($Mode) {
        "smoke" {
            Invoke-LocalPython @(
                ".\build_faebench_env.py",
                "--output", (Join-Path $DataRoot "normalized_trajectories\faebench.jsonl"),
                "--manifest", (Join-Path $DataRoot "pixie_research\faebench_manifest.json")
            )
            Invoke-LocalPython @(".\run_pixie_storyworld_sft.py", "--help")
            Invoke-LocalPython @(".\run_faebench_compare.py", "--help")
        }
        "action-train" {
            $slug = ModelSize-Slug -Value $ModelSize
            $tag = Default-Tag -Prefix "pixie_local_4gb_${slug}_action"
            $args = Storyworld-Local4GBArgs -Tag $tag -SelectedModel $ModelSize
            $args += @("--skip-mixed-pass", "--skip-prose-pass", "--action-save-steps", "1000", "--save-total-limit", "1")
            Invoke-LocalPython $args
        }
        "prose-train" {
            $slug = ModelSize-Slug -Value $ModelSize
            $tag = Default-Tag -Prefix "pixie_local_4gb_${slug}_prose"
            $args = Storyworld-Local4GBArgs -Tag $tag -SelectedModel $ModelSize
            $args += @("--skip-mixed-pass", "--skip-action-pass", "--prose-save-steps", "1000", "--save-total-limit", "1")
            Invoke-LocalPython $args
        }
        "prose-exact-train" {
            $slug = ModelSize-Slug -Value $ModelSize
            $tag = Default-Tag -Prefix "pixie_local_4gb_${slug}_prose_exact"
            $args = Storyworld-Local4GBArgs -Tag $tag -SelectedModel $ModelSize
            $args += @("--skip-mixed-pass", "--skip-action-pass", "--skip-prose-pass", "--run-prose-exact-pass", "--prose-exact-save-steps", "1000", "--save-total-limit", "1")
            Invoke-LocalPython $args
        }
        "faebench" {
            if (-not $AdapterPath) {
                throw "AdapterPath is required for faebench mode."
            }
            $slug = ModelSize-Slug -Value $ModelSize
            $tag = Default-Tag -Prefix "pixie_local_4gb_${slug}_faebench"
            $benchPath = Join-Path $DataRoot "normalized_trajectories\faebench.jsonl"
            $manifestPath = Join-Path $DataRoot "pixie_research\faebench_manifest.json"
            $outputPath = Join-Path $DataRoot "pixie_research\$tag.json"
            Invoke-LocalPython @(".\build_faebench_env.py", "--output", $benchPath, "--manifest", $manifestPath)
            Invoke-LocalPython @(
                ".\run_faebench_compare.py",
                "--models", $ModelSize,
                "--bench", $benchPath,
                "--adapter-path", "$ModelSize=$AdapterPath",
                "--output", $outputPath
            )
        }
    }
}
finally {
    Pop-Location
}
