--- Neovim configuration.
---
--- Requires Neovim 0.12+: plugins are managed by the built-in `vim.pack`, so
--- there is no third-party plugin manager to bootstrap. Plugin revisions are
--- pinned in `nvim-pack-lock.json`, which sits next to this file and is
--- version-controlled with it.

-- Leader keys must be set before plugins load: plugins capture their value at
-- load time.
vim.g.mapleader = " "
vim.g.maplocalleader = " "

-- ---------------------------------------------------------------------------
-- Options
-- ---------------------------------------------------------------------------
-- Only options that differ from the Neovim 0.12 defaults are set here. See
-- `:help nvim-defaults`: 'autoindent', 'autoread', 'backspace', 'compatible',
-- 'encoding', 'errorbells', 'hidden', 'hlsearch', 'incsearch', 'laststatus',
-- 'mousehide', 'ruler', 'showcmd', 'ttyfast', 'visualbell' and 'wrap' are all
-- already on, and 'history' already defaults to 10000.

local opt = vim.opt

-- Interface.
opt.number = true
opt.cursorline = true
opt.title = true
opt.lazyredraw = true
opt.mouse = "a" -- default is "nvi": also enable the mouse in command-line mode
opt.signcolumn = "yes" -- pin the gutter open so diagnostics don't shift text
opt.showmode = false -- the statusline already renders the mode
opt.timeoutlen = 500
opt.ttimeoutlen = 0

-- Editing.
opt.expandtab = true -- spaces instead of tabs
opt.tabstop = 4
opt.shiftwidth = 4
opt.softtabstop = 4
opt.virtualedit = "all"
opt.textwidth = 79
opt.colorcolumn = "80"
opt.foldmethod = "indent" -- automatically fold by indent level
opt.foldenable = false -- ... but have folds open by default

-- Searching.
opt.ignorecase = true
opt.smartcase = true
opt.showmatch = true

-- Swap files are noise. A persistent undo history is not: the previous config
-- promised "permanent undo levels" but only ever raised 'history'.
opt.swapfile = false
opt.undofile = true

-- Highlight tabs, trailing spaces and other suspicious characters.
-- Source: https://wincent.com/blog/making-vim-highlight-suspicious-characters
-- 'leadmultispace' draws the indent guides that the archived indentLine plugin
-- used to provide. Its width tracks 'shiftwidth'.
opt.list = true
opt.listchars = {
    nbsp = "¬",
    tab = "→ ",
    extends = "»",
    precedes = "«",
    trail = "•",
    leadmultispace = "┊   ",
}

-- 'clipboard' is deliberately left alone so that plain y/p keep using Vim
-- registers. The <Leader>y / <Leader>p mappings below reach the system
-- clipboard explicitly.

-- ---------------------------------------------------------------------------
-- Plugins
-- ---------------------------------------------------------------------------
-- Everything the previous config used a plugin for and Neovim now does on its
-- own has been dropped: deoplete and supertab (native LSP completion),
-- vim-polyglot and vim-css3-syntax (treesitter), incsearch.vim ('incsearch' and
-- 'hlsearch' are defaults), indentLine ('listchars' above), ALE (native LSP
-- diagnostics), vim-repeat (only needed by the vimscript plugins that are
-- gone), and the dead coveragepy.vim, vim-jade, po.vim, plist.vim mirrors.

vim.pack.add({
    -- Colorscheme. MIT-licensed and needs no Monokai Pro licence: it only
    -- reimplements the palettes. The "classic" filter set below is the closest
    -- match to the old crusoexia/vim-monokai.
    "https://github.com/loctvl842/monokai-pro.nvim",

    -- Syntax, folding and text objects. The `main` branch is the rewrite that
    -- targets Neovim 0.12; `master` is frozen for 0.11 and earlier.
    { src = "https://github.com/nvim-treesitter/nvim-treesitter", version = "main" },

    -- Statusline and its icons, replacing vim-airline and vim-devicons.
    "https://github.com/nvim-lualine/lualine.nvim",
    "https://github.com/nvim-tree/nvim-web-devicons",

    -- Git gutter, replacing vim-gitgutter.
    "https://github.com/lewis6991/gitsigns.nvim",

    -- Auto-pairs, replacing delimitMate.
    "https://github.com/windwp/nvim-autopairs",

    -- Multiple cursors. vim-multiple-cursors is deprecated by its own author
    -- in favour of this one.
    "https://github.com/mg979/vim-visual-multi",

    -- Formatting on demand, replacing vim-autoformat.
    "https://github.com/stevearc/conform.nvim",

    -- Surround, alignment and the file picker, replacing vim-surround,
    -- vim-easy-align and the <Leader>o mapping that pointed at a CtrlP that was
    -- never installed.
    "https://github.com/nvim-mini/mini.nvim",
})

require("monokai-pro").setup()
-- The filter is picked by the colorscheme name, not by setup(): `monokai-pro`
-- itself hardcodes the "pro" filter. "classic" is the closest match to the old
-- crusoexia/vim-monokai. Run `:colorscheme monokai-pro-<Tab>` to see the rest.
vim.cmd.colorscheme("monokai-pro-classic")

require("lualine").setup({
    options = { theme = "auto", globalstatus = true },
    -- vim-airline showed the buffer list in the tabline; keep that.
    tabline = { lualine_a = { { "buffers", show_filename_only = true } } },
})

require("gitsigns").setup()
require("nvim-autopairs").setup()

require("mini.surround").setup()
require("mini.align").setup()
require("mini.pick").setup()

require("conform").setup({
    formatters_by_ft = {
        python = { "ruff_format", "ruff_organize_imports" },
        sh = { "shfmt" },
        bash = { "shfmt" },
        zsh = { "shfmt" },
    },
})

-- ---------------------------------------------------------------------------
-- Treesitter
-- ---------------------------------------------------------------------------
-- Neovim bundles parsers for c, lua, markdown, query, vim and vimdoc only.
-- Anything else has to be compiled, which needs the tree-sitter CLI: skip the
-- install when it is missing rather than erroring on every startup.
require("nvim-treesitter").setup()

if vim.fn.executable("tree-sitter") == 1 then
    require("nvim-treesitter").install({
        "bash",
        "css",
        "diff",
        "dockerfile",
        "gitcommit",
        "gitignore",
        "html",
        "javascript",
        "json",
        "python",
        "toml",
        "typescript",
        "xml", -- also covers .plist
        "yaml",
    })
end

-- Highlighting is Neovim's job; the plugin only supplies parsers. pcall keeps
-- filetypes without a parser from raising an error.
vim.api.nvim_create_autocmd("FileType", {
    group = vim.api.nvim_create_augroup("treesitter_start", { clear = true }),
    callback = function(ev)
        pcall(vim.treesitter.start, ev.buf)
    end,
})

-- ---------------------------------------------------------------------------
-- Language servers
-- ---------------------------------------------------------------------------
-- Neovim core ships no server definitions, so both are declared inline. That
-- avoids pulling in nvim-lspconfig for two servers. Both binaries are pinned in
-- the repository's packages.toml.

vim.lsp.config("ruff", {
    cmd = { "ruff", "server" },
    filetypes = { "python" },
    root_markers = { "pyproject.toml", "ruff.toml", ".ruff.toml", ".git" },
})

-- Grammar and style checking for prose, which ALE used to drive.
vim.lsp.config("harper_ls", {
    cmd = { "harper-ls", "--stdio" },
    filetypes = { "gitcommit", "markdown", "rst", "text" },
    root_markers = { ".git" },
})

vim.lsp.enable({ "ruff", "harper_ls" })

-- Neovim 0.11+ already maps K, grn, gra, grr, gri, grt and <C-s>, so the only
-- thing left to turn on is completion. See `:help lsp-defaults`.
vim.api.nvim_create_autocmd("LspAttach", {
    group = vim.api.nvim_create_augroup("lsp_attach", { clear = true }),
    callback = function(ev)
        vim.lsp.completion.enable(true, ev.data.client_id, ev.buf, { autotrigger = true })
    end,
})

-- ---------------------------------------------------------------------------
-- Keymaps
-- ---------------------------------------------------------------------------
-- Source: https://sheerun.net/2014/03/21/how-to-boost-your-vim-productivity/
local map = vim.keymap.set

map("n", "<Leader>o", function()
    MiniPick.builtin.files()
end, { desc = "Find file" })
map("n", "<Leader>w", "<Cmd>write<CR>", { desc = "Save file" })

-- Copy & paste through the system clipboard.
map("v", "<Leader>y", '"+y')
map("v", "<Leader>d", '"+d')
map({ "n", "v" }, "<Leader>p", '"+p')
map({ "n", "v" }, "<Leader>P", '"+P')

-- Enter visual line mode.
map("n", "<Leader><Leader>", "V")

-- Leave Ex mode, for good.
-- Source: http://www.bestofvim.com/tip/leave-ex-mode-good/
map("n", "Q", "<Nop>")

map("n", "<Leader>f", function()
    require("conform").format({ lsp_format = "fallback" })
end, { desc = "Format buffer" })

-- ---------------------------------------------------------------------------
-- Autocommands
-- ---------------------------------------------------------------------------

-- Filetypes where trailing whitespace and non-breaking spaces carry meaning:
--   - Markdown ends a line with two spaces to force a hard line break.
--   - French typography requires a non-breaking space before ; : ! ? and
--     inside « quotation marks ».
-- The previous config rewrote both unconditionally on every save, which
-- silently destroyed them.
local PROSE_FILETYPES = {
    gitcommit = true,
    mail = true,
    markdown = true,
    plaintex = true,
    rst = true,
    tex = true,
    text = true,
    typst = true,
}

--- Substitute over the whole buffer without disturbing the cursor position,
--- the jumplist or the search register, all of which a bare `:%s` clobbers.
local function substitute(pattern, replacement)
    local view = vim.fn.winsaveview()
    vim.cmd(("keeppatterns keepjumps silent! %%s/%s/%s/e"):format(pattern, replacement))
    vim.fn.winrestview(view)
end

vim.api.nvim_create_autocmd("BufWritePre", {
    group = vim.api.nvim_create_augroup("clean_on_write", { clear = true }),
    callback = function(ev)
        local ft = vim.bo[ev.buf].filetype
        -- Outside of Markdown, trailing whitespace is only ever noise.
        if ft ~= "markdown" then
            substitute([[\s\+$]], "")
        end
        -- A non-breaking space is an invisible bug in code and correct
        -- typography in prose, so only strip it from code.
        if not PROSE_FILETYPES[ft] then
            substitute([[\%xa0]], " ")
        end
        -- Remove any byte order mark at the beginning.
        vim.bo[ev.buf].bomb = false
    end,
})

-- Prose is never hard-wrapped: let the renderer handle wrapping.
vim.api.nvim_create_autocmd("FileType", {
    group = vim.api.nvim_create_augroup("prose_no_wrap", { clear = true }),
    pattern = vim.tbl_keys(PROSE_FILETYPES),
    callback = function()
        vim.opt_local.textwidth = 0
        vim.opt_local.colorcolumn = ""
        vim.opt_local.formatoptions:remove("t")
    end,
})

-- Give execution permissions to newly created shebang (#!) files.
local shebang = vim.api.nvim_create_augroup("shebang_chmod", { clear = true })
vim.api.nvim_create_autocmd("BufNewFile", {
    group = shebang,
    callback = function(ev)
        vim.b[ev.buf].brand_new_file = true
    end,
})
vim.api.nvim_create_autocmd("BufWritePost", {
    group = shebang,
    callback = function(ev)
        if vim.b[ev.buf].brand_new_file and vim.fn.getline(1):match("^#!") then
            vim.system({ "chmod", "+x", ev.match })
        end
        vim.b[ev.buf].brand_new_file = nil
    end,
})

-- Briefly highlight whatever was just yanked.
vim.api.nvim_create_autocmd("TextYankPost", {
    group = vim.api.nvim_create_augroup("highlight_yank", { clear = true }),
    callback = function()
        vim.hl.on_yank()
    end,
})
