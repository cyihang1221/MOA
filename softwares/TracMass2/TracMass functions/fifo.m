function varargout=fifo(a,varargin)
%Magnus Åberg
persistent q first last count dim
DEBUG = false;
switch lower(a)
   case 'init'
      dim = [1e4 1];
      if nargin==2,
         dim =varargin{1};
      end
      q = nan(dim);
      first = 1;
      count = 0;
      last  = 0;
      if DEBUG
         disp('init')
         q'
         disp([first,last,count])
      end
      return
      
   case 'add'
      assert(nargin==2,'wrong number of aguments')
      x = varargin{1};
      if dim(2)==1,x = x(:);end
      k = size(x,1);
      
      if count+k> dim(1),
         [q,first,last,dim] = alloc(q,first,last,dim);
      elseif last+k>dim(1)
         [q,first,last] = shift(q,first,last);
      end
      ii = last + (1:k);
      q(ii,:) = x;
      count = count + k;
      last = last + k;
      if DEBUG
         disp('add')
         q'
         disp([first,last,count])
      end
      return
      
   case 'pop'
      if count==0,
         varargout{1}=[];
      else
         varargout{1}=q(first,:);
         first = first+1;
         count = count-1;
      end
      if count==0
         first = 1;
         last = 0;
      end
      if DEBUG
         disp('pop')
         q'
         disp([first,last,count])
      end
      return
      
   case 'isempty'
      varargout{1} = count==0;
      if DEBUG
         disp('')
         q'
         disp([first,last,count])
      end
      return
      
   case 'getall'
      varargout{1} = q(first:last);
      return
   otherwise
      error('unknown action')
end


function [q,first,last,dim]=alloc(q,first,last,dim)
tmp = q(first:last,:);
n = size(q,1);
dim(1) = n+dim(1);
q = nan(dim);
q(1:(last-first+1),:)=tmp;
last = last-first+1;
first = 1;


function [q,first,last] = shift(q,first,last)
n = last-first+1;
q(1:n,:) = q(first:last,:);
first = 1;
last = n;
q(n+1,:) = nan;
