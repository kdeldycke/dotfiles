" NEOBUNDLE {{{ ===============================================================

set nocompatible             " No to the total compatibility with the ancient vi


" NeoBundle auto-installation and setup {{{

" Auto installing NeoBundle
let iCanHazNeoBundle=1
let neobundle_readme=expand($HOME.'/.vim/bundle/neobundle.vim/README.md')
if !filereadable(neobundle_readme)
    echo "Installing NeoBundle.."
    echo ""
    silent !mkdir -p $HOME/.vim/bundle
    silent !git clone https://github.com/Shougo/neobundle.vim $HOME/.vim/bundle/neobundle.vim
    let iCanHazNeoBundle=0
endif

" Call NeoBundle
if has('vim_starting')
    set rtp+=$HOME/.vim/bundle/neobundle.vim/
endif
call neobundle#begin(expand($HOME.'/.vim/bundle/'))

" is better if NeoBundle rules NeoBundle (needed!)
NeoBundle 'Shougo/neobundle.vim'

" }}}


" BUNDLES (plugins administrated by NeoBundle) {{{

" Vimproc to asynchronously run commands (NeoBundle, Unite)
NeoBundle 'Shougo/vimproc', {
      \ 'build' : {
      \     'windows' : 'make -f make_mingw32.mak',
      \     'cygwin' : 'make -f make_cygwin.mak',
      \     'mac' : 'make -f make_mac.mak',
      \     'unix' : 'make -f make_unix.mak',
      \    },
      \ }

" Git
NeoBundle 'tpope/vim-fugitive'
NeoBundle 'airblade/vim-gitgutter'

" Color scheme
NeoBundle 'altercation/vim-colors-solarized.git'

" Syntax
NeoBundleLazy 'vim-scripts/JSON.vim', {'autoload': {'filetypes': ['json']}}
NeoBundleLazy 'vim-scripts/po.vim--gray', {'autoload': {'filetypes': ['po']}}
NeoBundleLazy 'vim-scripts/plist.vim', {'autoload': {'filetypes': ['plist']}}
NeoBundleLazy 'hunner/vim-plist', {'autoload': {'filetypes': ['plist']}}
NeoBundleLazy 'joedicastro/vim-markdown', {'autoload': {'filetypes': ['markdown']}}
NeoBundleLazy 'sophacles/vim-bundle-mako', {'autoload': {'filetypes': ['mako']}}
NeoBundle 'scrooloose/syntastic'

" Python
NeoBundle 'Shougo/neocomplete.vim'
NeoBundleLazy 'klen/python-mode', {'autoload': {'filetypes': ['python']}}
NeoBundle 'jmcantrell/vim-virtualenv'
NeoBundleLazy 'Yggdroot/indentLine', {'autoload': {'filetypes': ['python']}}
NeoBundleLazy 'alfredodeza/coveragepy.vim', {'autoload': {'filetypes': ['python']}}

" Text edition
NeoBundle 'delimitMate.vim'
NeoBundle 'tpope/vim-speeddating'
NeoBundle 'tpope/vim-surround'
NeoBundle 'tpope/vim-repeat'
NeoBundle 'tpope/vim-commentary'
NeoBundle 'terryma/vim-multiple-cursors'

" GUI
NeoBundle 'bling/vim-airline'

call neobundle#end()

" END BUNDLES }}}


" Auto install the plugins {{{

" First-time plugins installation
if iCanHazNeoBundle == 0
    echo "Installing Bundles, please ignore key map error messages"
    echo ""
    :NeoBundleInstall
endif

" Check if all of the plugins are already installed, in other case ask if we
" want to install them (useful to add plugins in the .vimrc)
NeoBundleCheck

" }}}


filetype plugin indent on      " Indent and plugins by filetype

" END NEOBUNDLE }}}



" VIM Setup {{{ ===============================================================

let mapleader = "\<Space>"
let maplocalleader=' '

scriptencoding utf-8
set encoding=utf-8              " setup the encoding to UTF-8
set ls=2                        " status line always visible

" Leader-based shortcuts {{{
" Source: http://sheerun.net/2014/03/21/how-to-boost-your-vim-productivity/
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
"}}}

" Copy & paste {{{
if has ('x') && has ('gui') " On Linux use + register for copy-paste
    set clipboard=unnamedplus
elseif has ('gui')          " On mac and Windows, use * register for copy-paste
    set clipboard=unnamed
endif
" Enable "bracketed paste mode". See: http://stackoverflow.com/a/7053522/31493
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
"}}}


" GUI {{{
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
"}}}


" Editing {{{
set expandtab                  " spaces instead of tabs
set tabstop=4                  " a tab = four spaces
set shiftwidth=4               " number of spaces for auto-indent
set softtabstop=4              " a soft-tab of four spaces
set backspace=indent,eol,start
set autoindent                 " set on the auto-indent
set foldmethod=indent          " automatically fold by indent level
set nofoldenable               " ... but have folds open by default"
set virtualedit=all
set textwidth=99
set colorcolumn=100
" highlight tabs and trailing spaces
" source: https://wincent.com/blog/making-vim-highlight-suspicious-characters
set listchars=nbsp:¬,eol:¶,tab:→\ ,extends:»,precedes:«,trail:•
" Leave Ex Mode, For Good
" source: http://www.bestofvim.com/tip/leave-ex-mode-good/
nnoremap Q <nop>
" }}}


" Searching {{{
set incsearch                   " incremental searching
set showmatch                   " show pairs match
set hlsearch                    " highlight search results
set smartcase                   " smart case ignore
set ignorecase                  " ignore case letters
" }}}


" History and permanent undo levels {{{
set history=1000
set undofile
set undoreload=1000
" }}}


" Colorscheme {{{
syntax enable                  " enable the syntax highlight
set background=dark            " set a dark background
let g:solarized_termtrans = 1
colorscheme solarized
" }}}


" Font
set guifont=Source\ Code\ Pro:h11


" Make a dir if no exists {{{
function! MakeDirIfNoExists(path)
    if !isdirectory(expand(a:path))
        call mkdir(expand(a:path), "p")
    endif
endfunction
" }}}


" Backups {{{
set backup
set noswapfile
set backupdir=$HOME/.vim/tmp/backup/
set undodir=$HOME/.vim/tmp/undo/
set directory=$HOME/.vim/tmp/swap/
set viminfo+=n$HOME/.vim/tmp/viminfo
" Make this dirs if no exists previously
silent! call MakeDirIfNoExists(&undodir)
silent! call MakeDirIfNoExists(&backupdir)
silent! call MakeDirIfNoExists(&directory)
" }}}


" Autoload configuration when this file changes ($MYVIMRC)
autocmd! BufWritePost vimrc source %


" Delete trailing whitespaces
autocmd BufWritePre,FileWritePost * :%s/\s\+$//e
" Replace all non-breakable spaces by simple spaces
" Source: http://nathan.vertile.com/find-and-replace-non-breaking-spaces-in-vim/
autocmd BufWritePre,FileWritePost * silent! :%s/\%xa0/ /g


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
let g:airline_theme = 'solarized'
let g:airline_enable_branch = 1
let g:airline_powerline_fonts = 1
let g:airline_detect_whitespace = 1
let g:airline#extensions#hunks#non_zero_only = 1
let g:airline#extensions#tabline#enabled = 2
let g:airline#extensions#tabline#fnamemod = ':t'
let g:airline#extensions#tabline#buffer_min_count = 1


" indentLine
let g:indentLine_char = '┊'
let g:indentLine_color_term = 239


" Syntastic
let g:syntastic_python_pylint_exe = "pylint2"
let g:syntastic_sh_checkers = ['shellcheck', 'sh']
let g:syntastic_error_symbol = '✘'
let g:syntastic_warning_symbol = '⚠'
let g:syntastic_style_error_symbol = '⚡'
let g:syntastic_style_warning_symbol = '⚡'


" PythonMode
let g:pymode_doc = 0
let g:pymode_lint_checkers = ['pylint', 'pep8', 'mccabe', 'pep257']
let g:pymode_lint_ignore = ''
let g:pymode_lint_cwindow = 0
let g:pymode_lint_todo_symbol = '⚠'
let g:pymode_lint_comment_symbol = '⑊'
let g:pymode_lint_visual_symbol = '⑆'
let g:pymode_lint_error_symbol = '✘'
let g:pymode_lint_info_symbol = '●'
let g:pymode_lint_pyflakes_symbol = '●'
let g:pymode_rope = 0


" FILETYPES  {{{ ==============================================================

" JSON
autocmd BufNewFile,BufRead *.json set ft=json
augroup json_autocmd
  autocmd!
  autocmd FileType json set autoindent
  autocmd FileType json set formatoptions=tcq2l
  autocmd FileType json set textwidth=78 shiftwidth=2
  autocmd FileType json set softtabstop=2 tabstop=8
  autocmd FileType json set expandtab
  autocmd FileType json set foldmethod=syntax
augroup END

" Plist
au BufRead,BufNewFile *.plist set filetype=plist
autocmd FileType plist NeoBundleSource vim-plist
autocmd FileType plist NeoBundleSource plist.vim

" Git commit
autocmd Filetype gitcommit setlocal spell textwidth=72

" END FILETYPES }}}



" END VIM SETUP }}}
" vim:foldmethod=marker
