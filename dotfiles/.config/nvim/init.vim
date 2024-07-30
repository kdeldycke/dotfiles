" Drop total compatibility with ancient vi.
if &compatible
  " `:set nocompatible` has many side effects. Therefore this should be done only when 'compatible' is set.
  set nocompatible
endif

" Figure out our config directory.
let config_dir = has("nvim") ? '~/.config/nvim' : '~/.vim'
let dein_repo = 'github.com/Shougo/dein.vim'
let dein_url = 'https://' . dein_repo . '.git'
let plugins_dir = config_dir . '/dein'
let dein_dir = plugins_dir . '/repos/' . dein_repo


" Auto-install package manager. Sources:
" https://github.com/Shougo/dein.vim#quick-start
" https://github.com/stuarthicks/dotfiles/blob/master/neovim/.config/nvim/init.vim
if empty(glob(dein_dir))
  exec 'silent !mkdir -p ' . dein_dir
  exec '!git clone ' . dein_url . ' ' . dein_dir
endif
exec 'set runtimepath^=' . dein_dir

call dein#begin(expand(plugins_dir))

" Package manager
call dein#add('Shougo/dein.vim')

" Color scheme
call dein#add('crusoexia/vim-monokai')

" GUI
call dein#add('vim-airline/vim-airline')
call dein#add('vim-airline/vim-airline-themes')
call dein#add('Yggdroot/indentLine')
call dein#add('airblade/vim-gitgutter')
call dein#add('alfredodeza/coveragepy.vim')
call dein#add('ervandew/supertab')
call dein#add('ryanoasis/vim-devicons')

" Syntax
call dein#add('sheerun/vim-polyglot')
call dein#add('digitaltoad/vim-jade')
call dein#add('hail2u/vim-css3-syntax')
call dein#add('vim-scripts/po.vim--gray')
call dein#add('vim-scripts/plist.vim', {'on_ft': 'plist'})
call dein#add('hunner/vim-plist', {'on_ft': 'plist'})

" Linters
call dein#add('w0rp/ale')

" Edition
call dein#add('Chiel92/vim-autoformat')
call dein#add('Shougo/deoplete.nvim')
call dein#add('Raimondi/delimitMate')
call dein#add('terryma/vim-multiple-cursors')
call dein#add('haya14busa/incsearch.vim')
call dein#add('junegunn/vim-easy-align')
call dein#add('tpope/vim-surround')
call dein#add('tpope/vim-repeat')

if has('nvim') == 0
  call dein#add('tpope/vim-sensible')
endif

call dein#end()


filetype plugin indent on      " Indent and plugins by filetype
syntax enable


if dein#check_install()
  call dein#install()
endif


let mapleader = "\<Space>"
let maplocalleader=' '

scriptencoding utf-8
set encoding=utf-8              " setup the encoding to UTF-8
set ls=2                        " status line always visible

" Leader-based shortcuts {{{
" Source: https://sheerun.net/2014/03/21/how-to-boost-your-vim-productivity/
" Type <Space>o to open a new file
nnoremap <Leader>o :CtrlP<CR>
" Type <Space>w to save file
nnoremap <Leader>w :w<CR>
" Copy & paste to system clipboard with <Space>p and <Space>y
vmap <Leader>y "+y
vmap <Leader>d "+d
nmap <Leader>p "+p
nmap <Leader>P "+P
vmap <Leader>p "+p
vmap <Leader>P "+P
" Enter visual line mode
nmap <Leader><Leader> V


" Copy & paste
if has ('x') && has ('gui') " On Linux use + register for copy-paste
    set clipboard=unnamedplus
elseif has ('gui')          " On mac and Windows, use * register for copy-paste
    set clipboard=unnamed
endif
" Enable 'bracketed paste mode'. See: https://stackoverflow.com/a/7053522/31493
if &term =~ "xterm.*"
    let &t_ti = &t_ti . "\e[?2004h"
    let &t_te = "\e[?2004l" . &t_te
    function XTermPasteBegin(ret)
        set pastetoggle=<Esc>[201~
        set paste
        return a:ret
    endfunction
    map <expr> <Esc>[200~ XTermPasteBegin("i")
    imap <expr> <Esc>[200~ XTermPasteBegin("")
    cmap <Esc>[200~ <nop>
    cmap <Esc>[201~ <nop>
endif


" GUI
set number
set mouse=a
set mousehide
set wrap
set cursorline
set ttyfast
set title
set showcmd
set hidden
set ruler
set lazyredraw
set autoread
set ttimeoutlen=0
" No annoying sound on errors
set noerrorbells
set novisualbell
set t_vb=
set tm=500


" Editing
set expandtab                  " spaces instead of tabs
set tabstop=4                  " a tab = four spaces
set shiftwidth=4               " number of spaces for auto-indent
set softtabstop=4              " a soft-tab of four spaces
set backspace=indent,eol,start
set autoindent                 " set on the auto-indent
set foldmethod=indent          " automatically fold by indent level
set nofoldenable               " ... but have folds open by default"
set virtualedit=all
set textwidth=79
set colorcolumn=80
" highlight tabs and trailing spaces
" source: https://wincent.com/blog/making-vim-highlight-suspicious-characters
set listchars=nbsp:¬,eol:¶,tab:→\ ,extends:»,precedes:«,trail:•
" Leave Ex Mode, For Good
" source: http://www.bestofvim.com/tip/leave-ex-mode-good/
nnoremap Q <nop>


" Searching
set incsearch      " incremental searching
set showmatch      " show pairs match
set hlsearch       " highlight search results
set smartcase      " smart case ignore
set ignorecase     " ignore case letters


" History and permanent undo levels
set history=1000


" Color scheme.
colorscheme monokai


" Font
" List available fonts with: fc-list | cut -d ':' -f 2 | sort | uniq
set guifont=SauceCodePro\ Nerd\ Font:h11


set noswapfile


" Delete trailing whitespaces
autocmd BufWritePre,FileWritePost * :%s/\s\+$//e
" Replace all non-breakable spaces by simple spaces
" Source: http://nathan.vertile.com/find-and-replace-non-breaking-spaces-in-vim/
autocmd BufWritePre,FileWritePost * silent! :%s/\%xa0/ /g
" Remove Byte Order Mark at the beginning
autocmd BufWritePre,FileWritePost * setlocal nobomb


" Execution permissions by default to shebang (#!) files
augroup shebang_chmod
  autocmd!
  autocmd BufNewFile  * let b:brand_new_file = 1
  autocmd BufWritePost * unlet! b:brand_new_file
  autocmd BufWritePre *
        \ if exists('b:brand_new_file') |
        \   if getline(1) =~ '^#!' |
        \     let b:chmod_post = '+x' |
        \   endif |
        \ endif
  autocmd BufWritePost,FileWritePost *
        \ if exists('b:chmod_post') && executable('chmod') |
        \   silent! execute '!chmod '.b:chmod_post.' "<afile>"' |
        \   unlet b:chmod_post |
        \ endif
augroup END


" Airline
set noshowmode
let g:airline_theme = 'molokai'
let g:airline_powerline_fonts = 1
let g:airline#extensions#hunks#non_zero_only = 1
let g:airline#extensions#tabline#enabled = 2
let g:airline#extensions#tabline#fnamemod = ':t'
let g:airline#extensions#tabline#left_sep = ' '
let g:airline#extensions#tabline#left_alt_sep = '|'
let g:airline#extensions#tabline#buffer_min_count = 1


" indentLine
let g:indentLine_char = '┊'
let g:indentLine_color_term = 239


" ALE config for linting.
let g:ale_sign_error = '✘'
let g:ale_sign_warning = '⚠'
let g:ale_lint_on_save = 1
let g:ale_lint_on_text_changed = 1
let g:ale_sign_column_always = 1
let g:ale_echo_msg_format = '[%linter%] %s'


" Git gutter
let g:gitgutter_max_signs = 10000


" JSON
" Disable concealing mode altogether.
let g:vim_json_syntax_conceal = 0


" Markdown
" Disable element concealing.
let g:vim_markdown_conceal = 0
let g:vim_markdown_conceal_code_blocks = 0


" Plist
au BufRead,BufNewFile *.plist set filetype=plist
