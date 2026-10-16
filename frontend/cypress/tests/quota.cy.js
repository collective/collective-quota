// End-to-end tests for volto-collective-quota against the acceptance backend
// (`make acceptance-backend-start` in backend/), which installs
// collective.quota. Every test starts from a fresh site.

const API = 'http://127.0.0.1:55001/plone';
const AUTH = { user: 'admin', pass: 'secret' };
const MB = 1024 * 1024;

// base64 of `size` zero bytes (size divisible by 3 keeps it exact).
const zeros = (size) => 'A'.repeat(Math.ceil(size / 3) * 4);

function createFile(id, size, title = id) {
  return cy
    .request({
      method: 'POST',
      url: API,
      headers: { Accept: 'application/json' },
      auth: AUTH,
      body: {
        '@type': 'File',
        id,
        title,
        file: {
          data: zeros(size),
          encoding: 'base64',
          filename: `${id}.bin`,
          'content-type': 'application/octet-stream',
        },
      },
    })
    .its('body');
}

function setQuota({ soft = null, hard = null, policy = null } = {}) {
  cy.setRegistry('collective.quota.soft_limit_mb', soft);
  cy.setRegistry('collective.quota.hard_limit_mb', hard);
  cy.setRegistry('collective.quota.over_limit_policy', policy);
}

function getUsage() {
  return cy
    .request({
      url: `${API}/@quota-usage`,
      headers: { Accept: 'application/json' },
      auth: AUTH,
    })
    .its('body');
}

describe('volto-collective-quota', () => {
  beforeEach(() => {
    cy.viewport('macbook-16');
  });

  context('over the soft limit', () => {
    beforeEach(() => {
      cy.createContent({
        contentType: 'Document',
        contentId: 'page',
        contentTitle: 'Page',
      });
      createFile('big', 1.5 * MB, 'Big file');
      createFile('medium', 0.75 * MB, 'Medium file');
      createFile('small', 0.3 * MB, 'Small file');
      setQuota({ soft: 1, hard: 10, policy: 'allow' });
      cy.autologin();
    });

    it('shows the banner on content pages, not on the summary pages', () => {
      cy.visit('/');
      cy.get('#collective-quota-banner')
        .should('have.attr', 'data-level', 'warning')
        .and('contain', 'Disk usage warning');
      cy.visit('/page');
      cy.get('#collective-quota-banner').should('exist');
      cy.get('#collective-quota-banner a').click();
      cy.url().should('match', /\/quota-usage$/);
      cy.get('#page-quota-usage h1').should('contain', 'Disk usage');
      cy.get('#collective-quota-banner').should('not.exist');
    });

    it('has a Disk usage entry in the user menu', () => {
      cy.visit('/');
      cy.get('#toolbar-personal').click();
      cy.get('#collective-quota-disk-usage').click();
      cy.url().should('match', /\/quota-usage$/);
    });

    it('lists the biggest items and changes the limit', () => {
      cy.visit('/quota-usage');
      cy.get('#quota-usage-items tbody tr').should('have.length', 3);
      cy.get('#quota-usage-items tbody tr')
        .first()
        .should('contain', 'Big file')
        .and('contain', '1.5 MB');
      cy.get('#quota-usage-total').should('contain', '2.6 MB');
      cy.get('#quota-usage-limits').contains('button', '10').click();
      cy.url().should('contain', 'limit=10');
      cy.get('#quota-usage-limits .active').should('contain', '10');
    });

    it('deletes selected items and reports the space freed', () => {
      cy.intercept('DELETE', '**/big').as('deleteBig');
      cy.intercept('DELETE', '**/medium').as('deleteMedium');
      cy.visit('/quota-usage');
      cy.get('[data-uid] input').eq(0).click({ force: true });
      cy.get('[data-uid] input').eq(1).click({ force: true });
      cy.get('#quota-delete-selected').should('contain', '(2)').click();
      cy.get('.collective-quota-delete-modal')
        .should('contain', 'Big file')
        .and('contain', 'Medium file');
      cy.get('.collective-quota-delete-modal')
        .contains('button', 'Delete')
        .click();
      cy.wait(['@deleteBig', '@deleteMedium']);
      cy.get('.Toastify').should('contain', 'freeing 2.2 MB');
      cy.get('#quota-usage-items tbody tr').should('have.length', 1);
      // Under the soft limit now: no banner on content pages.
      cy.visit('/page');
      cy.get('#main').should('exist');
      cy.get('#collective-quota-banner').should('not.exist');
    });

    it('rebuilds the usage data from the control panel', () => {
      cy.visit('/controlpanel/collective-quota');
      cy.get('.collective-quota-summary').should('contain', '2.6 MB');
      cy.get('#quota-rebuild').click();
      cy.get('.Toastify').should('contain', 'Usage data rebuilt');
    });
  });

  context('link integrity', () => {
    beforeEach(() => {
      createFile('linked', 0.3 * MB, 'Linked file').then((file) => {
        cy.request({
          method: 'POST',
          url: API,
          headers: { Accept: 'application/json' },
          auth: AUTH,
          body: {
            '@type': 'Document',
            id: 'page',
            title: 'Linking page',
            blocks: {
              title: { '@type': 'title' },
              text: {
                '@type': 'slate',
                plaintext: 'See the file',
                value: [
                  {
                    type: 'p',
                    children: [
                      { text: 'See the ' },
                      {
                        type: 'link',
                        data: { url: `../resolveuid/${file.UID}` },
                        children: [{ text: 'file' }],
                      },
                      { text: '' },
                    ],
                  },
                ],
              },
            },
            blocks_layout: { items: ['title', 'text'] },
          },
        });
      });
      cy.autologin();
    });

    it('warns about broken links before deleting', () => {
      cy.visit('/quota-usage');
      cy.get('[data-uid] input').first().click({ force: true });
      cy.get('#quota-delete-selected').click();
      cy.get('.collective-quota-delete-modal')
        .should('contain', 'Linking page')
        .contains('button', 'Delete item and break links')
        .click();
      cy.get('.Toastify').should('contain', 'Deleted 1 items');
      cy.get('#quota-usage-empty').should('exist');
      cy.request({
        url: `${API}/page`,
        headers: { Accept: 'application/json' },
        auth: AUTH,
      })
        .its('status')
        .should('eq', 200);
    });
  });

  context('anonymous', () => {
    beforeEach(() => {
      createFile('big', 1.5 * MB);
      setQuota({ soft: 1, hard: 10, policy: 'allow' });
    });

    it('never sees quota data', () => {
      cy.visit('/');
      cy.get('#main').should('exist');
      cy.get('#collective-quota-banner').should('not.exist');
      cy.request({ url: `${API}?expand=quota`, headers: { Accept: 'application/json' } })
        .its('body.@components')
        .should('not.have.property', 'quota');
    });

    it('is sent to the login form from the disk usage page', () => {
      cy.visit('/quota-usage', { failOnStatusCode: false });
      cy.url().should('contain', '/login');
    });
  });

  context('no limits', () => {
    beforeEach(() => {
      createFile('big', 1.5 * MB, 'Big file');
      cy.autologin();
    });

    it('shows no banner and a note on the disk usage page', () => {
      cy.visit('/');
      cy.get('#main').should('exist');
      cy.get('#collective-quota-banner').should('not.exist');
      cy.visit('/quota-usage');
      cy.get('#quota-usage-no-limits').should('exist');
      cy.get('#quota-usage-bar').should('not.exist');
      cy.get('#quota-usage-items tbody tr').should('have.length', 1);
    });
  });

  context('control panel', () => {
    beforeEach(() => {
      createFile('big', 1.5 * MB);
      cy.autologin();
    });

    it('saves limits, then resets them to the defaults', () => {
      cy.intercept('PATCH', '**/@controlpanels/collective-quota').as('patch');
      cy.visit('/controlpanel/collective-quota');
      cy.get('.collective-quota-summary').should('exist');
      cy.get('#field-soft_limit_mb').clear().type('1');
      cy.get('#field-hard_limit_mb').clear().type('2');
      cy.get('#toolbar-save').click();
      cy.wait('@patch');
      cy.get('.Toastify').should('contain', 'Changes saved');
      getUsage().its('level').should('eq', 'warning');
      cy.visit('/');
      cy.get('#collective-quota-banner').should('exist');

      cy.visit('/controlpanel/collective-quota');
      cy.get('#toolbar-quota-reset').click();
      cy.get('.ui.modal').contains('button', 'Reset to defaults').click();
      cy.wait('@patch');
      cy.get('.Toastify').should('contain', 'Settings reset');
      cy.get('.collective-quota-controlpanel').should(
        'contain',
        'Current value: 0 (default)',
      );
      getUsage().its('limits_configured').should('eq', false);
      cy.visit('/');
      cy.get('#main').should('exist');
      cy.get('#collective-quota-banner').should('not.exist');
    });
  });

  context('backend add-on not installed', () => {
    beforeEach(() => {
      createFile('big', 1.5 * MB);
      setQuota({ soft: 1, hard: 10, policy: 'allow' });
      cy.request({
        method: 'POST',
        url: `${API}/@addons/collective.quota/uninstall`,
        headers: { Accept: 'application/json' },
        auth: AUTH,
      });
      cy.autologin();
    });

    it('hides every piece and explains why on the page', () => {
      cy.visit('/');
      cy.get('#main').should('exist');
      cy.get('#collective-quota-banner').should('not.exist');
      cy.get('#toolbar-personal').click();
      cy.get('#toolbar-logout').should('exist');
      cy.get('#collective-quota-disk-usage').should('not.exist');
      cy.visit('/quota-usage');
      cy.get('#quota-usage-not-installed').should(
        'contain',
        'collective.quota is not installed on the backend.',
      );
    });
  });
});
